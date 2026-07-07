#include <thread>
#include<iostream>
#include <sys/sysinfo.h>
#include<algorithm>
#include<fstream>
#include<sstream>
#include<chrono>
#include<string>
#include<mutex>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <vector>

#include <opencv2/core/core.hpp>
// #include <sophus/se3.hpp>  // Para transformaciones SE(3)

//#include <GPS_Utils.h>

#include <Apos.h>
#include <Rmatrix.h>
#include <Rquat.h>
#include <Rvector.h>

#include <CAN_parser.h>
#include <processes/Pstreaming.h>
#include <processes/Pstreaming_rtsp.h>
#include <processes/Pdebugrecords.h>
#include <processes/Debug_msgs_subs_can.h>
#include <processes/Pcapturing.h>
#include <processes/Pcapturingemulation.h>
#include <processes/Pcameraemulation.h>
#include <processes/Debug_msgs_subs_print.h>
// #include <processes/Pvisual_odometry.h>

// #include"System.h" //ORB FILE

#include <csignal>

#include <Simple_config_parser.h>
#include <Vbn_session.h>
#include <Viewer_wrapper.h>
#include <Vbn_sil.h>
// #include <Remote_viewer_publisher.h>

#include <comms/Tcp_linux.h>
#include <Veronte_SIL.h>
// #include <Eigen/Dense>

#include <Orbsettings_vbn.h>
#include <Visual_window_dual.h>
#include <Cameraextrinsics.h>
#include <Stllist_shared.h> 
#include <Lm_logger.h>
#include <Lpf_buffer.h>
#include <Pcapturing_lpf_reader.h>
#include <Pcamera_lpf_reader.h>

#include <Debug_errors.h>

#include <System_daa.h>

// ------------------ Processes --------------------
std::thread* thread_camera = 0;
std::thread* thread_capturing = 0;
std::thread* thread_streaming = 0;
std::thread* thread_streaming_rtsp = 0;
std::thread* thread_debugging = 0;
std::thread* thread_vo = 0;
std::thread* thread_pat = 0;
std::thread* thread_mavlink = 0;
Vbn::Pdebugrecords* debugging = 0;
Vbn::Pstreaming* streaming = 0;
Vbn::Pstreaming_rtsp* streaming_rtsp = 0;
Vbn::Pcapturing* capturing = 0  ;
Vbn::Pcamera* camera = 0;
Vbn::Pcameraemulation* camera_emu = 0;
Vbn::Lpf_buffer* rtsp_buffer = 0;

// -------------------- Utils ---------------------
Vbn::Llhpframe* prev_lpf;
Vbn::Llhpframe* curr_lpf;
Vbn::Camerapinhole<Real, Real, Uint16>* cameramodel;
Vbn::Vbn_session* vbn_session;
Vbn::Simple_config_parser* parser = 0;
Vbn::Viewer_wrapper* viewer_wrapper = 0;
Vbn::Vbn_sil* vbn_sil = 0;

// -------------------- Comms ----------------------
CAN_parser* can0 = nullptr;
CAN_plnx* can_driver = nullptr;
Uint32 can_msg_id = 0x516U;
Vbn::Debug_msgs_subs_print* print_subs = 0;
Vbn::Debug_msgs_subs_can* can_subs = 0;

// -------------- Control variables ----------------
bool stop_process = false;
static bool daa_debug = true;

// --------------- General settings ---------------
int execution_mode = -1;
int n_features = 0;
int img_width = 0;          // Original img width
int img_height = 0;         // Original img height
int img_ch = 0;

int sz_queue_pcamera = 0;
bool use_color_streaming = false;

int memory_limit = 0;
std::string ip_streaming = "";
std::string path_debug = "";
static double time_fps = 0.0;

// --------------- Camera HW Config ----------------
std::vector<Vbn::Camera_dev_config> camera_configs;

// --------------------- ORB ----------------------
int th_ini = 0;
int th_min = 0;
Real scale_factor = 0.0;
Uint8 scales = 0;

// ------------------ GNSS DENIED ------------------
// ORB_SLAM3::System* SLAM = 0;
// Sophus::SE3f gTbc;
// Sophus::SE3f gTwb;
// Geo::Apos firstGPS;
// bool vision_fix = false;
bool isFirstGPS;
// Eigen::Quaternion<float> firstRotationBody;
// static Base::Tllh last_llh_est;
// static Eigen::Vector3f last_ypr_est;

// --------------------- RTSP -----------------------
int rtsp_port = 0;
H264_encoder_config encoder_config{};

// -------------------- DAA ------------------------
int input_width = 0;        // Img width for model input
int input_height = 0;       // Img height for model input
Real delta_heading = 0.0;
Real delta_elevation = 0.0;
int daa_status = -1;
std::vector<std::vector<float>> raw_detections;

// -------------------  VBN SIL --------------------
int last_id = -1;
double lat_gt = 0.0, lon_gt = 0.0, alt_gt = 0.0;
bool vsession = false;
std::string sil_ip = "";
int sil_port = 0;

// -------------------- LOGS -----------------------
std::vector<float> v_total_time;
std::vector<float> v_getlast_times;
Vbn::Lm_logger logger_slam;
Vbn::Lm_logger logger_capturing;
Vbn::Lm_logger logger_vo;
Vbn::Lm_logger logger_pat;


void parse_parameters();
void init_process_threads();

void process_frame(Vbn::System_daa& daa, Vbn::Llhpframe& lpf, cv::Mat& frame, double roll, double pitch, double yaw, double elapsed_time, Real& delta_heading, Real& delta_elevation);
void signalHandler(int signal);

int main(int argc, char **argv)
{
    struct sysinfo info;
    std::signal(SIGINT, signalHandler);
    std::signal(SIGSEGV, signalHandler);

    isFirstGPS = true;
    std::cout << "DAA 1.0.0" << std::endl;

    if(argc < 2)
    {
        std::cout << "Parameters: [DAA Config File]" << std::endl;
        return 1;
    }

    parser = &Vbn::Simple_config_parser::get_instance();
    parser->init(argv[1]);
    int ram_available = 0;
    int swap_available = 0;
    parser->GetRAMAvailable(ram_available);
    parser->GetSwapAvailable(swap_available);

    if (sysinfo(&info) == 0) {

        int swap = (info.totalswap)  / (1024*1024);
        int ram = (info.totalram) / (1024*1024);
        if(ram < ram_available)
        {
            if(swap < swap_available) {
                std::cout << "Insufficent RAM (less than " << ram_available/1000 << "GB) and swap not available (or swap size < " << swap_available << "GB)." << std::endl;
                return 1;
            }
        }
    }

    // Parse DAA parameters
    parse_parameters();

    // Verbose 
    switch (execution_mode)
    {
        case 0:
            std::cout << "[#] DAA: Normal Execution" << std::endl;
            break;
        case 1:
            std::cout << "[#] DAA: Execute with prerecords" << std::endl;
            break;
        case 2:
            std::cout << "[#] DAA: Recording" << std::endl;
            break;
        default:
            std::cout << "[#] DAA: Invalid mode; exiting ..." << std::endl;
            return 1;
    }

    // Setup ORB extractor
    Vbn::Orbsettings_vbn::set_limits(1);
    Vbn::Orbsettings_vbn::set_scales(scales);
    Vbn::Orbsettings_vbn::set_scale_factor(scale_factor);
    Vbn::Orbsettings_vbn& orbsettings = Vbn::Orbsettings_vbn::get_instance();
    orbsettings.get_orbsizes().push_back(2000);
    orbsettings.get_orbsizes().init_memmgr();
    Vbn::Iorbextractor::init_memmgr();
    Vbn::Orbsizes& orbs = orbsettings.get_instance().get_orbsizes();
    Vbn::Data::set_orbsizes(&orbs);

    // Setup Camera model
    Vbn::Cam_intr p_intrinsics;
    parser->GetCameraFX(p_intrinsics.fx);
    parser->GetCameraFY(p_intrinsics.fy);
    parser->GetCameraCX(p_intrinsics.cx);
    parser->GetCameraCY(p_intrinsics.cy);
    parser->GetCameraK1(p_intrinsics.k1);
    parser->GetCameraK2(p_intrinsics.k2);
    parser->GetCameraP1(p_intrinsics.p1);
    parser->GetCameraP2(p_intrinsics.p2);
    parser->GetCameraK3(p_intrinsics.k3);

    //La suma de las colas leidas por parametro para todos los procesos (capturing, vo, pat) 
    // debe ser menor o igual que este valor.
    // Se reserva esta cantidad de bloques para el almacenamiento de los datos.
    // Estos bloques son compartidos por todos los procesos
    Vbn::Tobject_shared_mgr<Vbn::Llhpframe*>::set_n_blocks(200);
    Vbn::Tobject_shared_mgr<Vbn::Llhpframe*>::set_mem_type(Base::Memmgr::external);
    Vbn::Tobject_shared_mgr<Vbn::Llhpframe*>::get_instance();

    Vbn::Camerapinhole<Real, Real, Uint16> cameramodel_left(p_intrinsics, orbs.mem_max());
    cameramodel = &cameramodel_left;

    prev_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::GRAYSCALE, Base::Memmgr::external);
    curr_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::GRAYSCALE, Base::Memmgr::external);
    // prev_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::BGR, Base::Memmgr::external);
    // curr_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::BGR, Base::Memmgr::external);

    Vbn::Visual_window_dual prev_window(*prev_lpf, 0);
    Vbn::Visual_window_dual curr_window(*curr_lpf, 0);
    Vbn::System_daa system_daa(*prev_lpf, *curr_lpf, prev_window, curr_window);

    can_driver = new CAN_plnx(parser->GetCanDevice(), parser->GetCanBitrate());
    can0 = new CAN_parser(*can_driver, can_msg_id);

    Base::Allocator& allocator = Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external);
    can_subs = allocator.allocate_new<Vbn::Debug_msgs_subs_can, CAN_parser*>(can0);
    print_subs = allocator.allocate_new<Vbn::Debug_msgs_subs_print>();

    //Cameraextrinsics
    Vbn::Cameraextrinsics camera_extrinsics(parser->GetCameraExtrinsicsRoll(), 
                                            parser->GetCameraExtrinsicsPitch(),
                                            parser->GetCameraExtrinsicsYaw(),
                                            parser->GetCameraExtrinsicsX(),
                                            parser->GetCameraExtrinsicsY(),
                                            parser->GetCameraExtrinsicsZ());


    std::cout << "[#] DAA: Iniciando procesos..." << std::endl;
    // Hardcoded normal execution, manage coproc threads
    init_process_threads();

    // init_daa();

    std::cout << "[#] DAA: Procesos iniciados" << std::endl;

    std::cout << "Memory usage [ System -- VBN ]: "
        << Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).used_mem()
        << "/" << Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).total_mem()
        << " (" << (Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).used_mem()*1.0/Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).total_mem())*100.0
        << "%)" << std::endl;

    Base::Memmgr::get_instance().close_allocation();

    std::cout << "Waiting execution flag" << std::endl;

    CAN_parser::DAA_vehicle_state vehicle_state_msg;
    vehicle_state_msg.base_message.lat = 0.0;
    vehicle_state_msg.base_message.lon = 0.0;
    vehicle_state_msg.base_message.alt = 0.0;
    vehicle_state_msg.base_message.roll = 0.0;
    vehicle_state_msg.base_message.pitch = 0.0;
    vehicle_state_msg.base_message.yaw = 0.0;
    vehicle_state_msg.vx = 1.0;
    vehicle_state_msg.vy = 2.0;
    vehicle_state_msg.vz = 3.0;
    vehicle_state_msg.fix = false;

    {
        do
        {
            Vbn::Data::Reader lpf = capturing->acquire_last();
            stop_process = !lpf->execution;
            can0->write_pose(vehicle_state_msg);
            std::cout << "Waiting for execution flag in captured data..." << std::endl;
            usleep(500000);
        }
        while(stop_process);
    }

    // If recording mode
    if (execution_mode == 2)
    {
        vehicle_state_msg.exec = true;
        while(true)
        {
            std::cout << "Recording..." << std::endl;
            can0->write_pose(vehicle_state_msg);
            if(stop_process)
            {
                break;
            }
            usleep(1000000);
        }
    }
    else
    {
        int last_frame_counter = 0;
        double last_ts = 0.0;
        // double lat, lon, alt;
        float r, p, y, r_gt, p_gt, y_gt;
        // bool fgps = false;
        cv::Mat in_frame(img_height, img_width, CV_8UC1);
        cv::Mat out_frame(img_height, img_width, CV_8UC3);

        // t_wait_start marks the instant we begin waiting for the next frame.
        // Keeping wait time and work time separate lets us tell apart producer
        // starvation (idle polling) from actual per-frame processing cost.
        std::chrono::high_resolution_clock::time_point t_wait_start = std::chrono::high_resolution_clock::now();

        while(true)
        {
            Vbn::Data::Reader lpf_reader = capturing->acquire_last();
            
            const bool new_frame_available = lpf_reader.valid() && lpf_reader->frame_counter > last_frame_counter;
            
            if (!new_frame_available)
            {
                lpf_reader.release(); // Release the handle if the frame is not valid or already processed
                usleep(500); // Sleep for 500 microseconds to avoid busy waiting when no new frame is available
            }
            else
            {
                // Time spent waiting for this frame (producer cadence / starvation).
                auto t_work_start = std::chrono::high_resolution_clock::now();
                double wait_time = std::chrono::duration<double, std::milli>(t_work_start - t_wait_start).count();

                bool is_next_frame = false;
                std::chrono::high_resolution_clock::time_point getlast_start = std::chrono::high_resolution_clock::now();
                last_frame_counter = lpf_reader->frame_counter;

                if (daa_debug)
                {
                    std::cout << "[#] Wait-for-frame time: " << wait_time << " ms" << std::endl;
                    std::cout << "[#] Acquired new frame with counter: " << last_frame_counter << std::endl;
                }

                Vbn::Data::full_copy_lpf(*lpf_reader, *curr_lpf);
                lpf_reader.release(); // Release the handle after copying the data

                last_ts = curr_lpf->timestamp;
                
                is_next_frame = last_frame_counter < (int)curr_lpf->frame_counter;
                vbn_sil->process_frame(*curr_lpf, lat_gt, lon_gt, alt_gt, r_gt, p_gt, y_gt, last_frame_counter, is_next_frame);
                std::chrono::high_resolution_clock::time_point getlast_innerend = std::chrono::high_resolution_clock::now();
                
                std::chrono::high_resolution_clock::time_point getlast_end = std::chrono::high_resolution_clock::now();
                double getlast_time = std::chrono::duration<double, std::milli>(getlast_end - getlast_start).count();
                if(stop_process)
                {
                    break;
                }

                if (daa_debug)
                {
                    std::cout << "[#] get_last() time: " << getlast_time << " ms" << std::endl;
                }

                // Encapsulate lpf frame to cv::Mat and convert to BGR for visualization
                // Compute copy time 
                auto cp_start = std::chrono::high_resolution_clock::now();
                memcpy(in_frame.data, curr_lpf->frame->first(), img_width * img_height);
                cv::cvtColor(in_frame, out_frame, cv::COLOR_GRAY2BGR);
                auto cp_end = std::chrono::high_resolution_clock::now();
                double cp_time = std::chrono::duration<double, std::milli>(cp_end - cp_start).count();
                if (daa_debug)
                {
                    std::cout << "[#] Frame copy and color conversion time: " << cp_time << " ms" << std::endl;
                }
                // ---------------------------------------------------------------------

                auto process_start = std::chrono::high_resolution_clock::now();
                process_frame(system_daa, *curr_lpf, out_frame, r, p, y, 0.0, delta_heading, delta_elevation);
                auto process_end = std::chrono::high_resolution_clock::now();
                double process_time = std::chrono::duration<double, std::milli>(process_end - process_start).count();

                if (daa_debug)
                {
                    std::cout << "[#] DAA processing time: " << process_time << " ms" << std::endl;
                }

                // PATCH for RTSP streaming in DAA
                // Overlay the YOLO detections on the visualization frame and publish it to the RTSP stream
                system_daa.draw_detections(out_frame);
                if (rtsp_buffer != nullptr)
                {
                    Vbn::Lpf_buffer::Writer rtsp_pub(*rtsp_buffer);
                    Vbn::Data::Writer rtsp_frame = rtsp_pub.write();
                    if (rtsp_frame.valid())
                    {
                        Vbn::Iimage annotated_bgr(out_frame.data,
                                                  static_cast<Uint32>(img_width),
                                                  static_cast<Uint32>(img_height),
                                                  Vbn::Iimage::BGR);
                        rtsp_frame->frame->copy_from(annotated_bgr);
                        rtsp_frame.commit();
                    }
                }

                // Updating prev_lpf for next iteration
                Vbn::Data::full_copy_lpf(*curr_lpf, *prev_lpf);

                // Work time = actual processing for this frame (excludes the wait above).
                auto t_work_end = std::chrono::high_resolution_clock::now();
                double work_time = std::chrono::duration<double, std::milli>(t_work_end - t_work_start).count();
                // Overall time = wait + work (end-to-end period between processed frames).
                double total_time = wait_time + work_time;

                // Time logs 
                if (daa_debug)
                {
                    std::cout << "[#] Work time: " << work_time << " ms" << std::endl;
                    std::cout << "[#] Overall time: " << total_time << " ms (" << 1.0 / (total_time/1000.0) << " FPS)"
                              << " | wait: " << wait_time << " ms, work: " << work_time << " ms" << std::endl;
                }

                v_total_time.push_back(total_time);
                v_getlast_times.push_back(getlast_time);

                // Restart the wait stopwatch for the next frame.
                t_wait_start = std::chrono::high_resolution_clock::now();
                usleep(500);
            }
        }

        // // Print mean, median and std deviation of process time
        // double mean_process_time = std::accumulate(v_process_times.begin(), v_process_times.end(), 0.0) / v_process_times.size();
        // std::vector<float> sorted_process_times = v_process_times;
        // std::sort(sorted_process_times.begin(), sorted_process_times.end());
        // double median_process_time = sorted_process_times[sorted_process_times.size() / 2];
        // double std_process_time = std::sqrt(std::accumulate(v_process_times.begin(), v_process_times.end(), 0.0, [mean_process_time](double acc, double t){
        //     return acc + (t - mean_process_time) * (t - mean_process_time);
        // }) / v_process_times.size());
        // std::cout << "Process time - Mean: " << mean_process_time << " ms, Median: " << median_process_time << " ms, Std Dev: " << std_process_time << " ms" << std::endl;

        system_daa.print_time_logs(v_total_time, v_getlast_times);

        std::cout << "Memory available: " << ((info.freeram + info.freeswap)-info.totalswap)  / (1024*1024) << " MB" << std::endl; // En algunos sistemas, freeram se puede usar como memoria disponible
    }


    std::cout << "DAA END"  << std::endl;

    for(int end_msgs = 0; end_msgs < 10; end_msgs++)
    {
        can0->write_pose(vehicle_state_msg);
        usleep(500000);
    }

    return 0;
}

void parse_parameters()
{
    // Parse ORB parameters from camera YAML
    std::string camera_config = parser->GetCameraCalibration();
    parser->init(camera_config);
    parser->GetORBextractorIniThFAST(th_ini);
    parser->GetORBextractorMinThFAST(th_min);
    scales = parser->GetORBextractorNLevels();
    parser->GetORBextractorScaleFactor(scale_factor);

    // Execution mode
    parser->GetRecordedMode(execution_mode);

    // Original image size
    parser->GetImageWidth(img_width);
    parser->GetImageHeight(img_height);

    // Parse traditional detector params
    parser->GetORBextractorNfeatures(n_features);

    // VBN SIL params
    parser->GetSILServerIP(sil_ip);
    parser->GetSILServerPort(sil_port);

    parser->GetMemoryLimit(memory_limit);
    parser->GetStreamingServerIP(ip_streaming);
    parser->GetVbnDebugPath(path_debug);
    Vbn::Debug_errors::set_save_path(path_debug);

    // Mavlink and RTSP ports
    parser->GetRTSPPort(rtsp_port);

    // Camera hardware configuration (simple iteration until not found)
    std::string camera_name, camera_id;
    bool camera_enabled;

    for (int i = 0; i < 10; i++) // Max 10 cameras
    {
        if (parser->GetCameraDevId(i, camera_id))
        {
            parser->GetCameraDevName(i, camera_name);
            parser->GetCameraDevEnabled(i, camera_enabled);

            Vbn::Camera_dev_config config;
            config.enabled = camera_enabled;
            config.dev_id = camera_id;
            camera_configs.push_back(config);

            std::cout << "[#] Camera " << i << ": " << camera_name 
                        << ", enabled: " << (camera_enabled ? "true" : "false")
                        << ", id: '" << camera_id << "'" << std::endl;
        }
        else
        {
            break; // No more cameras found
        }
    }
    
    std::cout << "[#] Found " << camera_configs.size() << " camera(s)" << std::endl;

    // Camera queue and streaming settings
    parser->GetSzQueueCamera(sz_queue_pcamera);
    parser->GetUseColorStreaming(use_color_streaming);

    encoder_config.bitrate         = 4000;
    encoder_config.vbv_max_bitrate = 4000;
    encoder_config.vbv_buffer_size = 4000;
    encoder_config.keyint_max      = 31;
    encoder_config.bframes         = 0;
    encoder_config.rc_lookahead    = 0;
    encoder_config.fps             = 30;
    encoder_config.threads         = 1;
    encoder_config.core_id         = 0;
    encoder_config.me_method       = 0;  /* X264_ME_DIA */
    encoder_config.subpel_refine   = 1;
    encoder_config.me_range        = 8;
    encoder_config.frame_reference = 1;
    encoder_config.aq_mode         = 0;
    encoder_config.trellis         = 0;
    std::snprintf(encoder_config.preset, sizeof(encoder_config.preset), "%s", "ultrafast");
    std::snprintf(encoder_config.tune, sizeof(encoder_config.tune), "%s", "zerolatency");

    int encoder_tmp = 0;
    std::string encoder_str;
    if (parser->GetEncoderBitrate(encoder_tmp))
    {
        encoder_config.bitrate = encoder_tmp;
    }
    if (parser->GetEncoderVbvMaxBitrate(encoder_tmp))
    {
        encoder_config.vbv_max_bitrate = encoder_tmp;
    }
    if (parser->GetEncoderVbvBufferSize(encoder_tmp))
    {
        encoder_config.vbv_buffer_size = encoder_tmp;
    }
    if (parser->GetEncoderKeyintMax(encoder_tmp))
    {
        encoder_config.keyint_max = encoder_tmp;
    }
    if (parser->GetEncoderBframes(encoder_tmp))
    {
        encoder_config.bframes = encoder_tmp;
    }
    if (parser->GetEncoderRcLookahead(encoder_tmp))
    {
        encoder_config.rc_lookahead = encoder_tmp;
    }
    if (parser->GetEncoderFps(encoder_tmp))
    {
        encoder_config.fps = encoder_tmp;
    }
    if (parser->GetEncoderThreads(encoder_tmp))
    {
        encoder_config.threads = encoder_tmp;
    }
    if (parser->GetEncoderCoreId(encoder_tmp))
    {
        encoder_config.core_id = encoder_tmp;
    }
    if (parser->GetEncoderMeMethod(encoder_tmp))
    {
        encoder_config.me_method = encoder_tmp;
    }
    if (parser->GetEncoderSubpelRefine(encoder_tmp))
    {
        encoder_config.subpel_refine = encoder_tmp;
    }
    if (parser->GetEncoderMeRange(encoder_tmp))
    {
        encoder_config.me_range = encoder_tmp;
    }
    if (parser->GetEncoderFrameReference(encoder_tmp))
    {
        encoder_config.frame_reference = encoder_tmp;
    }
    if (parser->GetEncoderAqMode(encoder_tmp))
    {
        encoder_config.aq_mode = encoder_tmp;
    }
    if (parser->GetEncoderTrellis(encoder_tmp))
    {
        encoder_config.trellis = encoder_tmp;
    }
    if (parser->GetEncoderPreset(encoder_str))
    {
        std::snprintf(encoder_config.preset, sizeof(encoder_config.preset), "%s", encoder_str.c_str());
    }
    if (parser->GetEncoderTune(encoder_str))
    {
        std::snprintf(encoder_config.tune, sizeof(encoder_config.tune), "%s", encoder_str.c_str());
    }
}

void init_process_threads()
{
    int shs;
    parser->GetSHS(shs);

    switch (execution_mode)
    {
        // Mode 0: Normal execution
        case 0:
        {
            const Vbn::Iimage::Type img_type = use_color_streaming ? Vbn::Iimage::YUV420 : Vbn::Iimage::GRAYSCALE;

            camera = new Vbn::Pcamera(img_width, img_height, img_type, sz_queue_pcamera, th_ini, th_min, camera_configs[0]);
            capturing = new Vbn::Pcapturing(shs, img_width, img_height, img_type, *camera, can0);//, &Vbn::Orbsettings_vbn::get_instance().get_orbsizes(), cameramodel);
            thread_camera = new std::thread(&Vbn::Pcamera::Run, camera);
            thread_capturing = new std::thread(&Vbn::Pcapturing::Run, capturing);
            std::cout << "Waiting capture: "  << std::endl;
            while(!capturing->ready())
            {
                usleep(100000);
            };
            std::cout << "End waiting capture: "  << std::endl;
            streaming = new Vbn::Pstreaming(capturing, ip_streaming.c_str());
            // thread_streaming = new std::thread(&Vbn::Pstreaming::Run, streaming);
            // PATCH for streaming stream the DAA YOLO detections over RTSP.
            // Instead of streaming raw camera frames, route the annotated frame produced
            // in the main loop through a shared buffer the RTSP server reads from.
            rtsp_buffer = new Vbn::Lpf_buffer(img_width, img_height, img_type, 3U);
            Vbn::ILlhpframe_reader* rtsp_reader = new Vbn::Lpf_buffer::Reader_last(*rtsp_buffer);
            streaming_rtsp = new Vbn::Pstreaming_rtsp(*rtsp_reader, rtsp_port, encoder_config);
            thread_streaming_rtsp = new std::thread(&Vbn::Pstreaming_rtsp::Run, streaming_rtsp);
            break;
        }
        // Mode 1: Execute with prerecords
        case 1:
        {
            const Vbn::Iimage::Type img_type = use_color_streaming ? Vbn::Iimage::YUV420 : Vbn::Iimage::GRAYSCALE;

            std::string prerecords_file;
            parser->GetRecordedPath(prerecords_file);
            int frame_init = parser->GetRecordedFrameInit();
            camera_emu = new Vbn::Pcameraemulation(prerecords_file.c_str(), img_width, img_height, img_type, th_ini, th_min, frame_init, vsession);
            capturing = new Vbn::Pcapturingemulation(img_width, img_height, img_type, *camera_emu);//, &Vbn::Orbsettings_vbn::get_instance().get_orbsizes(), cameramodel);
            vbn_session = new Vbn::Vbn_session(prerecords_file.c_str());
            thread_camera = new std::thread(&Vbn::Pcameraemulation::Run, camera_emu);
            thread_capturing = new std::thread(&Vbn::Pcapturing::Run, capturing);
            std::cout << "Waiting capture: "  << std::endl;
            while(!capturing->ready())
            {
                usleep(100000);
            };
            std::cout << "End waiting capture: "  << std::endl;
            streaming = new Vbn::Pstreaming(capturing, ip_streaming.c_str());
            // thread_streaming = new std::thread(&Vbn::Pstreaming::Run, streaming);
            // PATCH for streaming the DAA YOLO detections over RTSP.
            rtsp_buffer = new Vbn::Lpf_buffer(img_width, img_height, img_type, 3U);
            Vbn::ILlhpframe_reader* rtsp_reader = new Vbn::Lpf_buffer::Reader_last(*rtsp_buffer);
            streaming_rtsp = new Vbn::Pstreaming_rtsp(*rtsp_reader, rtsp_port, encoder_config);
            thread_streaming_rtsp = new std::thread(&Vbn::Pstreaming_rtsp::Run, streaming_rtsp);
            break;
        }
        // Mode 2: Record
        case 2:
        {
            camera = new Vbn::Pcamera(img_width, img_height, Vbn::Iimage::GRAYSCALE, sz_queue_pcamera, th_ini, th_min, camera_configs[0]);
            capturing = new Vbn::Pcapturing(shs, img_width, img_height, Vbn::Iimage::GRAYSCALE, *camera, can0);//, &Vbn::Orbsettings_vbn::get_instance().get_orbsizes()); //, &cameramodel);
            thread_camera = new std::thread(&Vbn::Pcamera::Run, camera);
            thread_capturing = new std::thread(&Vbn::Pcapturing::Run, capturing);
            std::cout << "Waiting capture "  << std::endl;
            while(!capturing->ready())
            {
                usleep(100000);
            };
            std::cout << "End waiting capture "  << std::endl;
            debugging = new Vbn::Pdebugrecords(capturing, path_debug);
            streaming = new Vbn::Pstreaming(capturing, ip_streaming.c_str());
            // streaming_rtsp = new Vbn::Pstreaming_rtsp(camera, target_rect, rtsp_port, encoder_config);
            thread_debugging = new std::thread(&Vbn::Pdebugrecords::Run, debugging);
            thread_streaming = new std::thread(&Vbn::Pstreaming::Run, streaming);
            // thread_streaming_rtsp = new std::thread(&Vbn::Pstreaming_rtsp::Run, streaming_rtsp);
            break;
        }
        default:
            break;
    }
}

void process_frame(Vbn::System_daa& daa, Vbn::Llhpframe& lpf, cv::Mat& frame, double roll, double pitch, double yaw, double elapsed_time, Real& delta_heading, Real& delta_elevation)
{
    daa.process_frame(lpf, frame, elapsed_time, delta_heading, delta_elevation);
    daa_status = static_cast<int>(daa.get_status());

    std::cout << "[STATUS]: DAA Status: " << daa_status << std::endl;
    std::cout << "[REACTION]: Output correction: yaw = " << delta_heading << "deg, pitch = " << delta_elevation << "deg" << std::endl;

    CAN_parser::DAA_obstacle_reaction daa_reaction_msg;
    const Base::Stlvector<Base::Stlvector<Real>*>& ttc_grid = daa.get_ttc_grid();
    for (int i = 0; i < parser->GetTTCCellsX(); i++)
    {
        for(int j = 0; j < parser->GetTTCCellsY(); j++)
        {
            daa_reaction_msg.ttc_matrix[j][i] = (*ttc_grid[i])[j];
        }
    }
    daa_reaction_msg.daa_status = daa_status;
    daa_reaction_msg.detections = daa.get_num_detections();
    can0->write_delta(delta_heading, delta_elevation);
    can0->write_obstacle_reaction(daa_reaction_msg);
}

void signalHandler(int signal) {
    if (signal == SIGINT) {
        std::cout << "\nFinishing...\n";
        if(!stop_process) stop_process = true;
        else exit(1);
    }
    else if(signal == SIGSEGV)
    {
        std::cout << "\n SEGMENTATION FAULT! \n";
        // if(can0 != NULL)
        // {
        //     std::cout << "Sending CAN messages\n";
        //     for(int end_msgs = 0; end_msgs < 10; end_msgs++)
        //     {
        //         can0->WritePose(0, 0, 0, 0, 0, 0, 1.0, 2.0, 3.0, false, false);
        //         usleep(500000);
        //     }
        // }
        std::cout << "Exit\n";
        exit(2);
    }
}