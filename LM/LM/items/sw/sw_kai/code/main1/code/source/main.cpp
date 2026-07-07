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
#include <processes/Pvisual_odometry.h>
#include <processes/Pcoms.h>

#include"System.h" //ORB FILE

#include <csignal>

#include <Simple_config_parser.h>
#include <Vbn_session.h>
#include <Viewer_wrapper.h>
#include <Vbn_sil.h>
#include <Remote_viewer_publisher.h>

#include <comms/Tcp_linux.h>
#include <Veronte_SIL.h>
// #include <Eigen/Dense>

#include <Orbsettings_vbn.h>
#include <processes/Ppoint_track.h>
#include <processes/Pmavlink_listener.h>
#include <Mavlink_subscriber.h>
#include <Mavlink_msg_rect.h>
#include <Visual_window_dual.h>
#include <System_vo.h>
#include <Cameraextrinsics.h>
#include <Stllist_shared.h> 
#include <Lm_logger.h>
#include <Lpf_buffer.h>
#include <Pcapturing_lpf_reader.h>
#include <Pcamera_lpf_reader.h>

#include <Debug_errors.h>

// ------------------ Processes --------------------
std::thread* thread_camera = 0;
std::thread* thread_capturing = 0;
std::thread* thread_streaming = 0;
std::thread* thread_streaming_rtsp = 0;
std::thread* thread_debugging = 0;
std::thread* thread_vo = 0;
std::thread* thread_pat = 0;
std::thread* thread_mavlink = 0;
std::thread* thread_coms = 0;
Vbn::Pdebugrecords* debugging = 0;
Vbn::Pstreaming* streaming = 0;
Vbn::Pstreaming_rtsp* streaming_rtsp = 0;
Vbn::Pcapturing* capturing = 0  ;
Vbn::Pcamera* camera = 0;
Vbn::Pcameraemulation* camera_emu = 0;
Vbn::Lpf_buffer* rtsp_buffer = 0;
Vbn::Pcoms* pcoms = 0;
    
Vbn::Pvisual_odometry* pvo = 0;
Vbn::Ppoint_track* ppat = 0;
Vbn::Pmavlink_listener* pmavlink_listener = 0;

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

// -------------- Process control ------------------
int enable_slam = 0;
int enable_vo = 0;
int enable_pat = 0;

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
ORB_SLAM3::System* SLAM = 0;
Sophus::SE3f gTbc;
Sophus::SE3f gTwb;
Geo::Apos firstGPS;
bool vision_fix = false;
bool isFirstGPS;
Eigen::Quaternion<float> firstRotationBody;
static Base::Tllh last_llh_est;
static Eigen::Vector3f last_ypr_est;

// --------------------- PAT -----------------------
Vbn::Rrect search_rect(0.0f, 0.0f, 0.0f, 0.0f);
volatile bool new_pat_selection = false;
Vbn::Mavlink_subscriber<Vbn::Mavlink_msg_rect>* mavlink_subscriber;
int mavlink_port = 0;
// RTSP streaming config
int rtsp_port = 0;
H264_encoder_config encoder_config{};

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

// GNSS Denied methods - ORBSLAM + VO
ORB_SLAM3::System* init_slam(const Vbn::Cameraextrinsics& camera_extrinsics);
void init_vo(const Vbn::Cameraextrinsics&);
void init_pat(const Vbn::Cameraextrinsics&, Vbn::ILlhpframe_reader&, Vbn::ILlhpframe_writer*);
void gnss_denied_process_frame(ORB_SLAM3::System* mpSLAM, Vbn::Llhpframe& lpf, CAN_parser* can);
void gnss_denied_generate_state_log_history(ORB_SLAM3::System* SLAM, std::string& state, Vbn::Llhpframe& lpf);
void vision_module_generate_state_log_history(Vbn::Pcapturing* capturing, std::string& state, Vbn::Llhpframe& lpf);

void shutdown_processes();

void print_time_logs();
void signalHandler(int signal);

int main(int argc, char **argv)
{
    struct sysinfo info;
    std::signal(SIGINT, signalHandler);
    std::signal(SIGSEGV, signalHandler);

    isFirstGPS = true;
    std::cout << "LM-PAT 1.0" << std::endl;

    if(argc < 2)
    {
        std::cout << "Parameters: [LM-PAT Config File]" << std::endl;
        return 1;
    }

    parser = &Vbn::Simple_config_parser::get_instance();
    parser->init(argv[1]);
    int ram_available = 0;
    int swap_available = 0;
    parser->GetRAMAvailable(ram_available);
    parser->GetSwapAvailable(swap_available);

    if (sysinfo(&info) == 0)
    {

        int swap = (info.totalswap)  / (1024*1024);
        int ram = (info.totalram) / (1024*1024);
        if(ram < ram_available)
        {
            if(swap < swap_available)
            {
                std::cout << "Insufficent RAM (less than " << ram_available/1000 << "GB) and swap not available (or swap size < " << swap_available << "GB)." << std::endl;
                return 1;
            }
        }
    }

    // Parse LM parameters
    parse_parameters();

    // Verbose 
    switch (execution_mode)
    {
        case 0:
            std::cout << "[#] LM: Normal Execution" << std::endl;
            break;
        case 1:
            std::cout << "[#] LM: Execute with prerecords" << std::endl;
            break;
        case 2:
            std::cout << "[#] LM: Recording" << std::endl;
            break;
        default:
            std::cout << "[#] LM: Invalid mode; exiting ..." << std::endl;
            return 1;
    }

    // Setup ORB extractor
    Vbn::Orbsettings_vbn::set_limits(1);
    Vbn::Orbsettings_vbn::set_scales(scales);
    Vbn::Orbsettings_vbn::set_scale_factor(scale_factor);
    Vbn::Orbsettings_vbn& orbsettings = Vbn::Orbsettings_vbn::get_instance();
    orbsettings.get_orbsizes().push_back(2000);
    //orbsettings.get_orbsizes().push_back(10000);
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

    // prev_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::BGR, Base::Memmgr::external);
    // curr_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::BGR, Base::Memmgr::external);
    prev_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::GRAYSCALE, Base::Memmgr::external);
    curr_lpf = Vbn::Data::build_lpf(img_width, img_height, Vbn::Iimage::GRAYSCALE, Base::Memmgr::external);

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

    std::cout << "[#] LM: Iniciando procesos..." << std::endl;
    

    // Initialize SLAM conditionally
    if (enable_slam == 1 && execution_mode != 2) // SLAM not needed in recording mode
    {
        std::cout << "[#] LM: Initializing SLAM..." << std::endl;
        SLAM = init_slam(camera_extrinsics);
        std::cout << "[#] LM: SLAM initialized!" << std::endl;
    }
    else
    {
        std::cout << "[#] LM: SLAM disabled by configuration" << std::endl;
    }
    
    // Para el Stdvector de Ireconstruction --> TODO
    // {
    //    Uint32 N = 1;
    //    Uint32 v_blocks[N] = {8100}, v_sizes[N] = {10050};
    //    Base::mem_reserve_patch<float>(N, v_blocks, v_sizes, Base::Memmgr::external);
    // }

    init_process_threads();
    
    // Launch PAT related processes conditionally
    if (enable_pat == 1 && execution_mode != 2) // PAT not needed in recording mode
    {
        std::cout << "[#] LM: Initializing PAT..." << std::endl;
        Vbn::ILlhpframe_reader& reader = *new Vbn::Pcapturing_lpf_reader(*capturing);
        Vbn::ILlhpframe_writer* writer = new Vbn::Lpf_buffer::Writer(*rtsp_buffer);
        init_pat(camera_extrinsics, reader, writer);
        std::cout << "[#] LM: PAT initialized!" << std::endl;
    }
    else
    {
        std::cout << "[#] LM: PAT disabled by configuration" << std::endl;
    }
    
    // Launch GNSS Denied related processes (VO, ORBSLAM) conditionally
    if (enable_vo == 1 && execution_mode != 2) // VO not needed in recording mode
    {
        std::cout << "[#] LM: Initializing VO..." << std::endl;
        init_vo(camera_extrinsics);
        std::cout << "[#] LM: VO initialized!" << std::endl;
    }
    else
    {
        std::cout << "[#] LM: VO disabled by configuration" << std::endl;
    }

    std::cout << "[#] LM: Procesos iniciados" << std::endl;

    std::cout << "[#] LM: Memory usage [ System -- VBN ]: "
        << Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).used_mem()
        << "/" << Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).total_mem()
        << " (" << (Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).used_mem()*1.0/Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external).total_mem())*100.0
        << "%)" << std::endl;

    Base::Memmgr::get_instance().close_allocation();

    // Initialize continuous log files (normal and prerecorded modes)
    if (execution_mode != 2)
    {
        std::string log_path;
        parser->GetVbnLogStatesPathFile(log_path);

        // SLAM log
        logger_slam.init(log_path + "_slam",
            "timestamp latitude longitude altitude roll pitch yaw fixGps vision_fix "
            "latitude_est longitude_est altitude_est roll_est pitch_est yaw_est "
            "th_ini th_min state state_gnss keypoints matches_track matches_opt "
            "matches_map matches_lm map_reset ransac_candidates reloc_matches "
            "time_grab_track time_track time_total");

        // Capturing pipeline log
        logger_capturing.init(log_path + "_capturing",
            "timestamp time_extract_ms time_undistort_ms time_kdtree_ms n_features");
        capturing->set_logger(&logger_capturing);

        // VO log
        logger_vo.init(log_path + "_vo",
            "timestamp dt vx vy vz p q r vel_mag vok "
            "t_raw_x t_raw_y t_raw_z "
            "tel_vx tel_vy tel_vz confidence "
            "nist_cand nist_degen nist_max_elem best_e_score best_e_zdom best_e_xyzr geom_fallback "
            "sigma1 sigma2 sigma3 sigma_ratio "
            "ransac_inliers ransac_matches ransac_inlier_pct ransac_best_iter ransac_early "
            "nGood1 nGood2 nGood3 nGood4 "
            "parallax1 parallax2 parallax3 parallax4 "
            "tel_sc1 tel_sc2 tel_sc3 tel_sc4 "
            "comb_sc1 comb_sc2 comb_sc3 comb_sc4 "
            "sel_hyp final_align tel_conflict all_vetoed "
            "nsimilar geom_margin tiebreaker_used "
            "rot_comp_deg r_res_d0 r_res_d1 r_res_d2 "
            "h_agl n_tri metric_baseline agl_used");
        if (pvo != nullptr)
        {
            pvo->set_logger(&logger_vo);
        }

        // PAT log
        logger_pat.init(log_path + "_pat",
            "timestamp pat_status time_detector_ms "
            "time_primary_ms time_preproc_ms time_infer_ms time_postproc_ms "
            "time_ekf_ms time_tracking_ms " 
            "dcf_box_area ekf_box_area tracked_box_area "
            "ekf_vx ekf_vy dcf_confidence tracking_confidence measurement_source");
        if (ppat != nullptr)
        {
            ppat->set_logger(&logger_pat);
        }
    }

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
    vehicle_state_msg.exec = false;
    
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
        double lat, lon, alt;
        float r_gt, p_gt, y_gt;
        bool fgps = false;

        std::chrono::high_resolution_clock::time_point t_start = std::chrono::high_resolution_clock::now();
        std::chrono::high_resolution_clock::time_point t_end = t_start;

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
                bool is_next_frame = false;
                std::chrono::high_resolution_clock::time_point getlast_start = std::chrono::high_resolution_clock::now();

                last_frame_counter = lpf_reader->frame_counter;
                std::cout << "[#] Acquired new frame with counter: " << last_frame_counter << std::endl;
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

                std::cout << "[#] get_last() time: " << getlast_time << " ms" << std::endl;

                // // GNSS Denied processing
                // std::cout << "[#] TH: " << static_cast<int>(curr_lpf->th_fast_ini) << " " << static_cast<int>(curr_lpf->th_fast_min) << std::endl;
                // std::cout << "[#] SHS param: " << curr_lpf->shs << std::endl;
                // SLAM->update_fast_thresholds(curr_lpf->th_fast_ini, curr_lpf->th_fast_min);
                // viewer_wrapper->clear_prerecords_gps(SLAM->mpTracker);
                gnss_denied_process_frame(SLAM, *curr_lpf, can0);
                // if(!curr_lpf->fixGps && SLAM->mpTracker->mStateGNSS == ORB_SLAM3::Tracking::GNSS_DENIED_MAPPED)
                // {
                //     viewer_wrapper->draw_reloc_route(*curr_lpf, SLAM->mpTracker, lat_gt, lon_gt, alt_gt, r_gt, p_gt, y_gt, vbn_sil);
                // }
                // viewer_wrapper->load_prerecords_gps(SLAM->mpTracker, vbn_session);

                // Updating prev_lpf for next iteration
                Vbn::Data::full_copy_lpf(*curr_lpf, *prev_lpf);

                t_end = std::chrono::high_resolution_clock::now();
                double total_time = std::chrono::duration<double, std::milli>(t_end - t_start).count();
                
                // Time logs 
                std::cout << "[#] Overall time: " << total_time << " ms (" << 1.0 / (total_time/1000.0) << " FPS)" << std::endl;

                v_total_time.push_back(total_time);
                v_getlast_times.push_back(getlast_time);

                if(SLAM)
                {
                    std::string state = "";
                    gnss_denied_generate_state_log_history(SLAM, state, *curr_lpf);
                    logger_slam.write(state);
                }

                t_start = t_end;
                usleep(500);
            }
        }

        std::cout << "[#] LM: Memory available: " << ((info.freeram + info.freeswap)-info.totalswap)  / (1024*1024) << " MB" << std::endl; // En algunos sistemas, freeram se puede usar como memoria disponible
    }

    std::cout << "--- LM END ---"  << std::endl;

    print_time_logs();
    shutdown_processes();

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
    parser->GetMavlinkPort(mavlink_port);
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

    // Process control parameters
    parser->GetProcessSlam(enable_slam);
    parser->GetProcessVO(enable_vo);
    parser->GetProcessPAT(enable_pat);

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
    // Mode 0: Normal execution
    switch (execution_mode)
    {
        case 0:
        {
            const Vbn::Iimage::Type img_type = use_color_streaming ? Vbn::Iimage::YUV420 : Vbn::Iimage::GRAYSCALE;

            pcoms = new Vbn::Pcoms();
            thread_coms = new std::thread(&Vbn::Pcoms::Run, pcoms);
            camera = new Vbn::Pcamera(img_width, img_height, img_type, sz_queue_pcamera, th_ini, th_min, camera_configs[0]);
            capturing = new Vbn::Pcapturing(shs, img_width, img_height, img_type, *camera, can0, &Vbn::Orbsettings_vbn::get_instance().get_orbsizes(), cameramodel);
            thread_camera = new std::thread(&Vbn::Pcamera::Run, camera);
            thread_capturing = new std::thread(&Vbn::Pcapturing::Run, capturing);
            std::cout << "Waiting capture: "  << std::endl;
            while(!capturing->ready())
            {
                usleep(100000);
            };
            std::cout << "End waiting capture: "  << std::endl;
            // debugging = new Vbn::Pdebugrecords(capturing, img_width, img_height, 1, n_features, path_debug);
            streaming = new Vbn::Pstreaming(capturing, ip_streaming.c_str());
            Vbn::ILlhpframe_reader* rtsp_reader;
            if(enable_pat)
            {
                rtsp_buffer = new Vbn::Lpf_buffer(img_width, img_height, img_type, 3U);
                rtsp_reader = new Vbn::Lpf_buffer::Reader_last(*rtsp_buffer);
            }
            else
            {
                rtsp_reader = new Vbn::Pcamera_lpf_reader(*camera);     
            }
            streaming_rtsp = new Vbn::Pstreaming_rtsp(*rtsp_reader, rtsp_port, encoder_config);
            // thread_debugging = new std::thread(&Vbn::Pdebugrecords::Run, debugging);
            // thread_streaming = new std::thread(&Vbn::Pstreaming::Run, streaming);
            thread_streaming_rtsp = new std::thread(&Vbn::Pstreaming_rtsp::Run, streaming_rtsp);
            break;
        }
        // Mode 1: Execute with prerecords
        case 1:
        {
            const Vbn::Iimage::Type img_type = use_color_streaming ? Vbn::Iimage::YUV420 : Vbn::Iimage::GRAYSCALE;

            pcoms = new Vbn::Pcoms();
            thread_coms = new std::thread(&Vbn::Pcoms::Run, pcoms);

            std::string prerecords_file;
            parser->GetRecordedPath(prerecords_file);
            int frame_init = parser->GetRecordedFrameInit();
            camera_emu = new Vbn::Pcameraemulation(prerecords_file.c_str(), img_width, img_height, img_type, th_ini, th_min, frame_init, vsession);
            capturing = new Vbn::Pcapturingemulation(img_width, img_height, img_type, *camera_emu, &Vbn::Orbsettings_vbn::get_instance().get_orbsizes(), cameramodel);
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
            Vbn::ILlhpframe_reader* rtsp_reader;
            if(enable_pat)
            {
                rtsp_buffer = new Vbn::Lpf_buffer(img_width, img_height, img_type, 3U);
                rtsp_reader = new Vbn::Lpf_buffer::Reader_last(*rtsp_buffer);
            }
            else
            {
                rtsp_reader = new Vbn::Pcamera_lpf_reader(*camera_emu);     
            }
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

ORB_SLAM3::System* init_slam(const Vbn::Cameraextrinsics& camera_extrinsics)
{
    // Build Tbc (body-to-camera) SE3 from config parser extrinsics
    gTbc = Sophus::SE3f(camera_extrinsics.Rbc(), camera_extrinsics.tbc());

    // World-to-body fixed geodetic convention (NED to body)
    Eigen::AngleAxisf qy90(90 * M_PI / 180.0, Eigen::Vector3f::UnitY());
    Eigen::AngleAxisf qx90(90 * M_PI / 180.0, Eigen::Vector3f::UnitX());
    gTwb = Sophus::SE3f(qy90.inverse() * qx90.inverse(), Eigen::Vector3f(0, 0, 0));

    Base::Allocator& allocator = Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external);

    std::string voc_path, camera_calib_path;
    parser->GetVocFile(voc_path);
    parser->GetCameraCalibration(camera_calib_path);

    static ORB_SLAM3::System SLAM(voc_path, camera_calib_path, ORB_SLAM3::System::MONOCULAR,true, 0, "");
    SLAM.subscribe_msgs_debug(print_subs);
    int viewer_port = 0;
    // parser->GetViewerPort(viewer_port);
    // static ORB_SLAM3::Remote_viewer_publisher viewer_pub(viewer_port);
    // if (viewer_pub.is_connected())
    // {
    //     SLAM.subscribe_viewer(&viewer_pub);
    // }
    SLAM.subscribe_msgs_debug(can_subs);

    viewer_wrapper = allocator.allocate_new<Vbn::Viewer_wrapper, const Geo::Apos&, const Sophus::SE3f&>(firstGPS, gTbc);
    vbn_sil = allocator.allocate_new<Vbn::Vbn_sil, const std::string&, int, const Geo::Apos&, const Sophus::SE3f&>(sil_ip, sil_port, firstGPS, gTbc);
    vsession = vbn_sil->get_vsession();

    return &SLAM;
}

void init_vo(const Vbn::Cameraextrinsics& camera_extrinsics)
{
    Vbn::Pvisual_odometry::Params params;
    params.width = img_width;
    params.height = img_height;
    params.img_type = Vbn::Iimage::GRAYSCALE;
    params.limit = 0;
    params.lk_gate_radius = parser->GetMatcherLKGateRadius();
    params.lowe_dist_thresh = parser->GetMatcherHammingDist();
    params.orb_hamming_thresh = parser->GetMatcherHammingDist();
    params.ransac_earlyend = parser->GetVbnVORansacEarlyEnd();
    params.ransac_iterations = parser->GetVbnVORansacIterations();
    params.ransac_min_iterations = parser->GetVbnVORansacMinIterations();
    params.ransac_error_threshold_px = parser->GetVbnVORansacErrorThreshold();
    params.min_good_threshold = parser->GetVbnVOMinGoodThreshold();
    params.sz_features = Vbn::Data::get_orbsizes().mem_max();
    params.rotation_compensation_enabled = parser->GetVbnVORotationCompensation();
    params.solver_mode = parser->GetVbnVOSolverMode();
    params.terrain_elevation_m = parser->GetVbnVOTerrainElevation();
    params.altitude_is_agl = parser->GetVbnVOAltitudeIsAGL();
    params.adaptive_baseline = parser->GetVbnVOAdaptiveBaseline();
    params.baseline_max_lookback = parser->GetVbnVOBaselineMaxLookback();
    params.agl_min_tri_points = parser->GetVbnVOAglMinTriPoints();
    params.scale_filter_enabled = parser->GetVbnVOScaleFilterEnabled();
    params.scale_median_window = parser->GetVbnVOScaleMedianWindow();
    params.scale_reject_factor = parser->GetVbnVOScaleRejectFactor();
    params.match_search_radius = parser->GetVbnVOMatchSearchRadius();

    pvo = new Vbn::Pvisual_odometry(capturing, 
        params,
        camera_extrinsics,
        firstGPS,
        *cameramodel);
    // pvo->subscribe(streaming);
    pvo->subscribe_msgs_debug(can_subs);

    thread_vo = new std::thread(&Vbn::Pvisual_odometry::Run, pvo);
}

void init_pat(const Vbn::Cameraextrinsics& camera_extrinsics, Vbn::ILlhpframe_reader& lpf_reader, Vbn::ILlhpframe_writer* lpf_writer)
{
    img_ch = 1;
    Vbn::Ppoint_track::Params_pat params;
    params.width = img_width;
    params.height = img_height;
    params.channel = img_ch;
    params.sz_features = Vbn::Orbsettings_vbn::get_instance().get_orbsizes().mem_max();

    ppat = new Vbn::Ppoint_track(lpf_reader, lpf_writer, params, search_rect, camera_extrinsics, firstGPS, *cameramodel, new_pat_selection);
    ppat->set_debug_stream(streaming);  // Temporary: energy detector debug visualization
    ppat->subscribe_msgs_debug(can_subs);
    // ppat->subscribe_msgs_debug(print_subs);
    thread_pat = new std::thread(&Vbn::Ppoint_track::Run, ppat);
    // mavlink_subscriber = new Vbn::Mavlink_subscriber<Vbn::Mavlink_msg_rect>(ip_streaming.c_str(), mavlink_port, parser->GetFPS());
    mavlink_subscriber = new Vbn::Mavlink_subscriber<Vbn::Mavlink_msg_rect>(mavlink_port, parser->GetFPS());
    pmavlink_listener = new Vbn::Pmavlink_listener(*curr_lpf, search_rect, new_pat_selection);
    pmavlink_listener->subscribe(mavlink_subscriber);
    thread_mavlink = new std::thread(&Vbn::Pmavlink_listener::run, pmavlink_listener);   
}

void gnss_denied_process_frame(ORB_SLAM3::System* mpSLAM, Vbn::Llhpframe& lpf, CAN_parser* can)
{
    cv::Mat frame(lpf.frame->get_height(), lpf.frame->get_width(), CV_8UC1);
    frame.data = lpf.frame->first();
    //cv::Mat frame = lpf.mat;
    double x, y, z;
    bool gps_lost = false;
    Eigen::Vector3f ypr;
    ypr[0] = lpf.roll;
    ypr[1] = lpf.pitch;
    ypr[2] = lpf.yaw;

    Base::Tllh llh; //(setear gps)
    llh.ll.lat = lpf.latitude * (M_PI/180.0); // grad to rad
    llh.ll.lon = lpf.longitude * (M_PI/180.0); // grad to rad
    llh.h      = lpf.altitude;

    //if primera posicion -> guardar
    if(isFirstGPS)
    {
        if(!lpf.fixGps)
        {
            return;
        }
        firstGPS.set_llh(llh);
        Maverick::Rquat veronte_quat;
        veronte_quat.ypr2quat(lpf.yaw, lpf.pitch, lpf.roll);
        firstRotationBody.x() = veronte_quat[Maverick::Rquat::qi];
        firstRotationBody.y() = veronte_quat[Maverick::Rquat::qj];
        firstRotationBody.z() = veronte_quat[Maverick::Rquat::qk];
        firstRotationBody.w() = veronte_quat[Maverick::Rquat::qs];
        //firstRotationBody = Eigen::Quaternion<float>(veronte_quat[Maverick::Rquat::qs], 
        //                                     veronte_quat[Maverick::Rquat::qi], 
        //                                     veronte_quat[Maverick::Rquat::qj], 
        //                                     veronte_quat[Maverick::Rquat::qk]).inverse(); //Veronte quaternion is inverse respect Eigen

        last_llh_est = llh;
        last_ypr_est = ypr;
        isFirstGPS = false;
    }

    std::vector<ORB_SLAM3::IMU::Point> imu_values;

    //VLIBS//
    Geo::Apos pos(llh);
    Maverick::Rvector3 output; //output in NED
    firstGPS.relthis(pos, output);
    
    gps_lost = !lpf.fixGps;

    Sophus::SE3f slamEstimated, slamEstimatedScaled;
    //if(!gps->gps.gps_lost){

    Maverick::Rquat veronte_quat;
    Eigen::AngleAxisf rollAngle(lpf.roll, Eigen::Vector3f::UnitX());
    Eigen::AngleAxisf pitchAngle(lpf.pitch, Eigen::Vector3f::UnitY());
    Eigen::AngleAxisf yawAngle(lpf.yaw, Eigen::Vector3f::UnitZ());
    
    veronte_quat.ypr2quat(lpf.yaw, lpf.pitch, lpf.roll);

    Eigen::Matrix<float, 3, 1> position(output[Maverick::Rvector3::vx], output[Maverick::Rvector3::vy], output[Maverick::Rvector3::vz]);
    Eigen::Quaternion<float> Rb =   yawAngle * pitchAngle * rollAngle ;

    Sophus::SE3f Twc = Sophus::SE3f(Rb, position)*gTbc;
    Sophus::SE3f Tcw = Twc.inverse();
    //Sophus::SE3f Tcw = Twc;
    //END VLIBS//
    
    //Eigen::HouseholderQR<Eigen::Matrix3f> qr(roty180*orientation*rotz45*rotz45*rotx45*rotx45);

    if (!mpSLAM)
    {
        return;
    }

    if(!gps_lost)
    {
        //mpSLAM->TrackMonocular(frame, lpf.timestamp, vision_fix, imu_values, "", &Tcw, true, &gTbc, false);
        mpSLAM->TrackMonocular(frame, *lpf.features, lpf.timestamp, vision_fix, "", &Tcw, true, &gTbc, false);
    }else
    {
        //ESTIMATE SLAM POSE//
        //slamEstimated = mpSLAM->TrackMonocular(frame, lpf.timestamp, vision_fix, imu_values, "", &Tcw, true, &gTbc, true);
        slamEstimated = mpSLAM->TrackMonocular(frame, *lpf.features, lpf.timestamp, vision_fix, "", &Tcw, true, &gTbc, true);

        ORB_SLAM3::Map* map = mpSLAM->GetAtlas()->GetCurrentMap(ORB_SLAM3::Atlas::TRACKING);
        //CONVERT SLAM POSE TO GPS//
        //double scale = (*mpSLAM->GetAtlas()->GetCurrentMap()->GetGPSRotationCS() * Eigen::Vector3f::Ones()).norm();
        Eigen::Matrix3f cs = *map->GetGPSRotationCS();
        const Sophus::SE3f initialGPS = *map->GetInitialGPS();
        const Sophus::SE3f secondGPS = *map->GetSecondGPS();
        const Sophus::SE3f initialSlamGPS_mapped = *map->GetInitialGPSMapped();
        
        mpSLAM->GetTracking()->ScalePoseFromMap0(slamEstimated.inverse(), slamEstimatedScaled);

        //OpticalCamera -> Body//
        slamEstimatedScaled = slamEstimatedScaled * gTbc.inverse();

        //VLIBS//
        //float r,p,y, 
        float stamp = -1;
        Eigen::Quaternionf qw = slamEstimatedScaled.unit_quaternion();
        Eigen::Matrix<float, 3, 1> position = slamEstimatedScaled.translation();
        Maverick::Rvector3 positionNEDEstimated(position.x(),
                                             position.y(),
                                             position.z());

        //TODO world estimated to roll pitch yaw
        ypr = qw.toRotationMatrix().eulerAngles(2, 1, 0);
        Geo::Apos actual_GPS(firstGPS.get_llh());
        llh = firstGPS.get_llh();
        actual_GPS.move_rn(positionNEDEstimated);

        llh = actual_GPS.get_llh();
        cv::Mat empty;
        
        last_llh_est = llh;
        last_ypr_est = ypr;

        debugging->step_debug_records(path_debug.c_str(), "estimation", 0, lpf);

    }

    CAN_parser::DAA_vehicle_state vehicle_msg;
    vehicle_msg.base_message.lat   = last_llh_est.ll.lat * (180.0 / M_PI);
    vehicle_msg.base_message.lon   = last_llh_est.ll.lon * (180.0 / M_PI);
    vehicle_msg.base_message.alt   = last_llh_est.h;
    vehicle_msg.base_message.roll  = last_ypr_est[0];
    vehicle_msg.base_message.pitch = last_ypr_est[1];
    vehicle_msg.base_message.yaw   = last_ypr_est[2];
    vehicle_msg.vx                 = 1.0;
    vehicle_msg.vy                 = 2.0;
    vehicle_msg.vz                 = 3.0;
    vehicle_msg.fix                = vision_fix;
    vehicle_msg.exec               = true;
    can->write_pose(vehicle_msg);

    vbn_sil->tcp_send_pose(last_llh_est.ll.lat  * (180.0/M_PI), last_llh_est.ll.lon  * (180.0/M_PI), last_llh_est.h, last_ypr_est[0], last_ypr_est[1], last_ypr_est[2], 1.0, 2.0, 3.0, alt_gt, lon_gt, lat_gt, vision_fix);
}

void gnss_denied_generate_state_log_history(ORB_SLAM3::System* SLAM, std::string& state, Vbn::Llhpframe& lpf)
{
        std::stringstream ss_state1;
        //recName << "/run/media/nvme0n1p1/flight_records/" << date << "/" << filename <<".txt";
        //std::ofstream recordFile(recName.str(), std::ios::app);
        ss_state1 << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
        << lpf.timestamp << " "
        << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
        << lpf.latitude << " " << lpf.longitude << " " << lpf.altitude << " " 
        << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
        << lpf.roll << " " << lpf.pitch << " " << lpf.yaw << " "
        << std::fixed << std::setprecision(std::numeric_limits<bool>::digits10)
        << lpf.fixGps << " " << vision_fix << " "
        << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
        << last_llh_est.ll.lat * (180.0/M_PI) << " " << last_llh_est.ll.lon * (180.0/M_PI) << " " << last_llh_est.h << " " 
        << std::fixed << std::setprecision(std::numeric_limits<float>::digits10)
        << last_ypr_est[0] << " " << last_ypr_est[1] << " " << last_ypr_est[2] << " "
        << std::fixed << std::setprecision(std::numeric_limits<int>::digits10)
        << static_cast<int>(lpf.th_fast_ini) << " " << static_cast<int>(lpf.th_fast_min) << " ";

        std::string state2 = "";
        SLAM->get_state(state2);

        std::stringstream ss_state3;
        ss_state3 << std::fixed << std::setprecision(std::numeric_limits<double>::digits10)
        << time_fps;

        state += ss_state1.str();
        state += state2;
        state += ss_state3.str();
}

void shutdown_processes()
{
    if (execution_mode != 2)
    {
        logger_slam.close();
        logger_capturing.close();
        logger_vo.close();
    }

    if (SLAM)
    {
        SLAM->Shutdown();
    }
    delete capturing;      

    CAN_parser::DAA_vehicle_state shutdown_msg;
    shutdown_msg.base_message = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
    shutdown_msg.vx           = 1.0;
    shutdown_msg.vy           = 2.0;
    shutdown_msg.vz           = 3.0;
    shutdown_msg.fix          = false;
    shutdown_msg.exec         = false;
    for(int end_msgs = 0; end_msgs < 10; end_msgs++)
    {
        can0->write_pose(shutdown_msg);
        usleep(500000);
    }

}

void print_time_logs()
{
    if (v_total_time.empty() || v_getlast_times.empty())
    {
        std::cout << "No timing data available." << std::endl;
        return;
    }

    // Calculate statistics for total time
    double sum_total = 0.0;
    for (const auto& time : v_total_time)
    {
        sum_total += time;
    }
    double mean_total = sum_total / v_total_time.size();

    double sum_sq_diff_total = 0.0;
    for (const auto& time : v_total_time)
    {
        sum_sq_diff_total += (time - mean_total) * (time - mean_total);
    }
    double std_dev_total = std::sqrt(sum_sq_diff_total / v_total_time.size());

    std::vector<float> sorted_total = v_total_time;
    std::sort(sorted_total.begin(), sorted_total.end());
    double median_total = sorted_total.size() % 2 == 0 
        ? (sorted_total[sorted_total.size()/2 - 1] + sorted_total[sorted_total.size()/2]) / 2.0
        : sorted_total[sorted_total.size()/2];

    // Calculate statistics for capture time
    double sum_cap = 0.0;
    for (const auto& time : v_getlast_times)
    {
        sum_cap += time;
    }
    double mean_cap = sum_cap / v_getlast_times.size();

    double sum_sq_diff_cap = 0.0;
    for (const auto& time : v_getlast_times)
    {
        sum_sq_diff_cap += (time - mean_cap) * (time - mean_cap);
    }
    double std_dev_cap = std::sqrt(sum_sq_diff_cap / v_getlast_times.size());

    std::vector<float> sorted_cap = v_getlast_times;
    std::sort(sorted_cap.begin(), sorted_cap.end());
    double median_cap = sorted_cap.size() % 2 == 0 
        ? (sorted_cap[sorted_cap.size()/2 - 1] + sorted_cap[sorted_cap.size()/2]) / 2.0
        : sorted_cap[sorted_cap.size()/2];

    // Print results
    std::cout << "\n========== PERFORMANCE STATISTICS ==========" << std::endl;
    std::cout << "Total Time: " << mean_total << " ± " << std_dev_total << " ms (median: " << median_total << " ms)" << std::endl;
    std::cout << "Capture Time: " << mean_cap << " ± " << std_dev_cap << " ms (median: " << median_cap << " ms)" << std::endl;
    std::cout << "==============================================\n" << std::endl;
}

void signalHandler(int signal)
{
    if (signal == SIGINT)
    {
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
