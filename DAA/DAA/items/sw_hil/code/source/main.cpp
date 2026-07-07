#include<iostream>
#include <can_hil.h>
#include <sys/sysinfo.h>
#include <vid_emul.h>
#include <img_hil.h>
#include <filesystem>
#include <vector>
#include <string>
#include <fstream>
#include <thread>
#include <ctime>
#include <filesystem> 


void loadRecordfile(std::string records_file, std::vector<std::vector<std::string>>& values);
void saveEstimationFile(std::string error_file, std::vector<std::vector<double>> error_vector);

void readCAN();
bool hil_exec;

Can_hil can0("can0", 1000000);
std::vector<std::vector<double>> position_error;

// CURRENT VALUES
double lat, lon, alt;
float roll, pitch, yaw, timestamp;
bool fix, execution = false;

int main(int argc, char **argv) {

	clock_t begin, end;
	float time_spent;
    float vx, vy, vz;
    uint32_t shs; 

    if(argc < 2){ 
        std::cout << "Parameters: [Records file]" << std::endl;
        return 1;
    }

    Vid_emul* vid_tx = new Vid_emul();

    void* img_ptr = vid_tx->get_frame_ptr();
    Img_hil img(img_ptr, 1280, 980);

    std::cout << "Start with: "<< argv[1] << std::endl;
    int frame_idx = 0;

    std::vector<std::vector<std::string>> values;
    std::string records_file = argv[1]; 
    //RECORD FILE LOADING
    loadRecordfile(records_file, values);


    int n_frame;
    std::vector<std::string> row;
    float prev_timestamp = 0;
    std::cout << "Records: "<< values.size() << std::endl;
    hil_exec = true;   
    
    // START UP Sequence
    // std::thread canRead_thread(readCAN);
    // while(execution == false)
    // {
    //     (void)vid_tx->send_frame();
    //     can0.WritePose(0, 0, 0, 0, 0, 0, 0, 960, true, true);
    //     sleep(1);
    // }
    
    for(n_frame = 0; n_frame < values.size(); n_frame++) {
	    begin = clock(); 
        std::vector<double> error_row;
        row  = values[n_frame];
        std::ostringstream filename;
        filename << std::setw(6) << std::setfill('0') << row[0];
        std::cout << "Record entry: "<< filename.str() << std::endl;
        // img.get_img((records_file.substr(0, records_file.find_last_of('/'))+"/"+filename.str()+".bmp").c_str());

        lat = std::stod(row[1]);
        lon = std::stod(row[2]);
        alt = std::stod(row[3]);
        roll = std::stod(row[4]);
        pitch = std::stod(row[5]);
        yaw = std::stod(row[6]);
        timestamp = std::stod(row[7]);
        fix = std::stod(row[8]);

        // std::cout << lat << " " << lon << " " << alt << " " << roll << " " << pitch << " " << yaw << " " << timestamp << " " << fix << std::endl;

        // (void)vid_tx->send_frame();
        can0.WritePose(lat, lon, alt, roll, pitch, yaw, timestamp, 960, fix, true);

	    end = clock();
	    time_spent = (double)(end - begin); //in microseconds
        float ms2sleep = (((timestamp - prev_timestamp) * 1000) - time_spent / 1000.0);
        //printf("Real Time spent: %f ms, expected time: %f, time to wait: %f\n", time_spent / 1000.0, (timestamp - prev_timestamp) * 1000, ms2sleep);
        if(ms2sleep > 0 && n_frame != 0)
        {
            //if(ms2sleep > 500) usleep(500 * 1000);
            //else 
            //usleep(ms2sleep * 1000);
        } 
        //usleep(50 * 1000);
       
        prev_timestamp = timestamp;
        usleep(50000);
    }
    
    std::cout << "Waiting for VNB SW ends." << std::endl;
    while(execution == 1){
        can0.WritePose(lat, lon, alt, roll, pitch, yaw, timestamp, 960, fix, false);
        usleep(1000000);
    }

    hil_exec = false;  
    saveEstimationFile("estimation.txt",position_error);

    std::cout << "Estimation file created" << std::endl;
    // canRead_thread.join();  
    std::cout << "END" << std::endl;
        
    return 0;
}


void readCAN(){

    double lat_est, lon_est, alt_est;
    float roll_est, pitch_est, yaw_est;
    float vx, vy, vz;
    bool fix_est;

    while(hil_exec){
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
        if(!fix){
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
    
    for(int idx; idx < error_vector.size(); idx++){
        std::vector<double> error_row = error_vector[idx];
        recordFile << idx << " "
        << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
        << error_row[0] << " " << error_row[1] << " " <<error_row[2] << " " 
        << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
        << error_row[3] << " " << error_row[4] << " " << error_row[5]<< " "<< error_row[6] <<std::endl;
    }
    recordFile.close();
}





void loadRecordfile(std::string records_file, std::vector<std::vector<std::string>>& values){

    std::ifstream file(records_file);
    if (!file.is_open()) {
        std::cerr << "File can't be open." << std::endl;
    }
    

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream ss(line);
        std::string value;
        std::vector<std::string> row;
        while (ss >> value) {
            row.push_back(value);
        }

        values.push_back(row);
    }
    values.erase(values.begin());

    std::cout << "File loaded." << std::endl;

}
