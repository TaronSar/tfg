#include <iostream>
#include <can_hil.h>
#include <sys/sysinfo.h>
#include <unistd.h>
#include <vid_emul.h>
#include <img_hil.h>
#include <filesystem>
#include <vector>
#include <string>
#include <fstream>
#include <thread>
#include <ctime>
#include <filesystem>
#include <chrono>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fb.h>
#include <cstring>
#include <opencv2/imgcodecs.hpp>


void loadRecordfile(std::string records_file, std::vector<std::vector<std::string>>& values);
void saveEstimationFile(std::string error_file, std::vector<std::vector<double>> error_vector);
void readCAN();

bool hil_exec;

Can_hil can0("can0", 1000000);
std::vector<std::vector<double>> position_error;

/// Current pose values shared with CAN read thread
double lat, lon, alt;
float roll, pitch, yaw, timestamp;
bool fix, execution = false;


int main(int argc, char **argv)
{

	clock_t begin, end;
	float time_spent;
    float vx, vy, vz;
    uint32_t shs; 

    /// Validate minimum arguments
    if(argc < 2)
    { 
        std::cout << "Parameters: [Records file] [--start N] [--hdmi] [--resolution WxH]" << std::endl;
        return 1;
    }

    /// Parse CLI options
    int start_frame = 0;
    bool use_hdmi = false;
    int target_w = 0, target_h = 0;
    for (int i = 2; i < argc; i++)
    {
        std::string arg(argv[i]);
        if (arg == "--hdmi")
        {
            use_hdmi = true;
        }
        else if (arg == "--resolution" && i + 1 < argc)
        {
            std::string res(argv[++i]);
            size_t xpos = res.find('x');
            if (xpos != std::string::npos)
            {
                target_w = std::atoi(res.substr(0, xpos).c_str());
                target_h = std::atoi(res.substr(xpos + 1).c_str());
            }
        }
        else if (arg == "--start" && i + 1 < argc)
        {
            start_frame = std::atoi(argv[++i]);
        }
    }

    const char* fb_dev = use_hdmi ? "/dev/fb1" : "/dev/fb0";
    std::cout << "Display output: " << (use_hdmi ? "HDMI" : "DisplayPort") << " (" << fb_dev << ")" << std::endl;

    /// Clear DP framebuffer on startup to avoid stale image
    int fb0_fd = open("/dev/fb0", O_RDWR);
    if (fb0_fd >= 0)
    {
        struct fb_var_screeninfo vinfo;
        struct fb_fix_screeninfo finfo;
        ioctl(fb0_fd, FBIOGET_VSCREENINFO, &vinfo);
        ioctl(fb0_fd, FBIOGET_FSCREENINFO, &finfo);
        size_t fb0_size = finfo.line_length * vinfo.yres;
        void* fb0_ptr = mmap(NULL, fb0_size, PROT_WRITE, MAP_SHARED, fb0_fd, 0);
        if (fb0_ptr != MAP_FAILED)
        {
            memset(fb0_ptr, 0, fb0_size);
            munmap(fb0_ptr, fb0_size);
        }
        close(fb0_fd);
        std::cout << "DP (fb0) cleared" << std::endl;
    }

    /// Hide console cursor to keep framebuffer clean
    system("echo 0 > /sys/class/graphics/fbcon/cursor_blink 2>/dev/null");
    system("echo -ne '\\033[?25l' > /dev/tty0 2>/dev/null");

    /// Initialize VDMA/MIPI video pipeline
    Vid_emul* vid_tx = new Vid_emul();
    void* img_ptr = vid_tx->get_frame_ptr();

    /// Load flight record CSV
    std::vector<std::vector<std::string>> values;
    std::string records_file = argv[1]; 
    loadRecordfile(records_file, values);

    /// Auto-detect output resolution from first image if not specified via CLI
    if (target_w == 0 || target_h == 0)
    {
        std::ostringstream first_fn;
        first_fn << std::setw(6) << std::setfill('0') << values[0][0];
        std::string first_img = records_file.substr(0, records_file.find_last_of('/')) + "/" + first_fn.str() + ".jpg";
        cv::Mat sample = cv::imread(first_img, cv::IMREAD_UNCHANGED);
        if (!sample.empty())
        {
            target_w = sample.cols;
            target_h = sample.rows;
        }
        else
        {
            target_w = 1920;
            target_h = 1080;
        }
    }
    std::cout << "Output resolution: " << target_w << "x" << target_h << std::endl;

    Img_hil img(img_ptr, 640, 480, fb_dev, target_w, target_h);

    std::cout << "Start with: "<< argv[1] << std::endl;
    int frame_idx = 0;

    int n_frame;
    std::vector<std::string> row;
    float prev_timestamp = 0;
    std::cout << "Records: "<< values.size() << std::endl;
    hil_exec = true;   
    
    /// Main playback loop: iterate through recorded frames
    std::cout << "Starting from frame: " << start_frame << std::endl;
    for(n_frame = start_frame; n_frame < values.size(); n_frame++)
    {
        auto frame_start = std::chrono::steady_clock::now();
        
        std::vector<double> error_row;
        row  = values[n_frame];
        std::ostringstream filename;
        filename << std::setw(6) << std::setfill('0') << row[0];
        std::cout << "Record entry: "<< filename.str() << std::endl;

        /// Load image and send to framebuffer + VDMA
        img.get_img((records_file.substr(0, records_file.find_last_of('/'))+"/"+filename.str()+".jpg").c_str());

        /// Parse pose data from record
        lat = std::stod(row[1]);
        lon = std::stod(row[2]);
        alt = std::stod(row[3]);
        roll = std::stod(row[4]);
        pitch = std::stod(row[5]);
        yaw = std::stod(row[6]);
        timestamp = std::stod(row[7]);
        fix = std::stod(row[8]);

        /// Transmit frame and pose over MIPI and CAN
        (void)vid_tx->send_frame();
        can0.WritePose(lat, lon, alt, roll, pitch, yaw, timestamp, 960, fix, true);

        /// Synchronize playback speed with record timestamps
        if (n_frame > start_frame)
        {
            float dt_record_ms = (timestamp - prev_timestamp) * 1000.0f;
            auto elapsed = std::chrono::steady_clock::now() - frame_start;
            float elapsed_ms = std::chrono::duration<float, std::milli>(elapsed).count();
            float sleep_ms = dt_record_ms - elapsed_ms;
            if (sleep_ms > 0)
            {
                usleep((useconds_t)(sleep_ms * 1000));
            }
        }
       
        prev_timestamp = timestamp;
    }
    
    /// Wait for VBN software to finish processing
    std::cout << "Waiting for VNB SW ends." << std::endl;
    while(execution == 1)
    {
        can0.WritePose(lat, lon, alt, roll, pitch, yaw, timestamp, 960, fix, false);
        usleep(1000000);
    }

    hil_exec = false;  
    saveEstimationFile("estimation.txt", position_error);

    std::cout << "Estimation file created" << std::endl;
    // canRead_thread.join();  
    std::cout << "END" << std::endl;
        
    return 0;
}


void readCAN()
{

    double lat_est, lon_est, alt_est;
    float roll_est, pitch_est, yaw_est;
    float vx, vy, vz;
    bool fix_est;

    /// Continuously read CAN estimations and compute error
    while(hil_exec)
    {
        std::vector<double> error_row;

        // can0.ReadPose(lat_est, lon_est, alt_est, roll_est, pitch_est, yaw_est, vx, vy, vz, fix_est, execution);

        error_row.push_back(lat_est);
        error_row.push_back(lon_est);
        error_row.push_back(alt_est);
        error_row.push_back(roll_est);
        error_row.push_back(pitch_est);
        error_row.push_back(yaw_est);
        error_row.push_back(timestamp);

        position_error.push_back(error_row);
        std::cout << "Execution: " << execution << std::endl;
        if(!fix)
        {
            std::cout << "ESTIMATION ERROR: "
            << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
            << lat_est - lat  << " " << lon_est - lon << " " << alt_est - alt << " " 
            << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
            << roll_est - roll << " " << pitch_est - pitch << " " << yaw_est - yaw << std::endl;
        }
    }
}


void saveEstimationFile(std::string error_file, std::vector<std::vector<double>> error_vector) {
    std::stringstream recName;
    recName << error_file;
    std::ofstream recordFile(recName.str(), std::ios::app);
    
    /// Write each estimation row: idx lat lon alt roll pitch yaw timestamp
    for(int idx = 0; idx < error_vector.size(); idx++)
    {
        std::vector<double> error_row = error_vector[idx];
        recordFile << idx << " "
        << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
        << error_row[0] << " " << error_row[1] << " " <<error_row[2] << " " 
        << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
        << error_row[3] << " " << error_row[4] << " " << error_row[5]<< " "<< error_row[6] <<std::endl;
    }
    recordFile.close();
}


void loadRecordfile(std::string records_file, std::vector<std::vector<std::string>>& values)
{

    std::ifstream file(records_file);
    if (!file.is_open()) {
        std::cerr << "File can't be open." << std::endl;
    }

    /// Parse whitespace-delimited values, skip header row
    std::string line;
    while (std::getline(file, line))
    {
        std::istringstream ss(line);
        std::string value;
        std::vector<std::string> row;
        while (ss >> value)
        {
            row.push_back(value);
        }
        values.push_back(row);
    }
    values.erase(values.begin());

    std::cout << "File loaded." << std::endl;
}
