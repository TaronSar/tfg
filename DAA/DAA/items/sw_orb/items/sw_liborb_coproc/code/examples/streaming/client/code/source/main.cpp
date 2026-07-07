
#include <iostream>
#include <cstdlib> // Para system()
#include <chrono>
#include <fstream>
#include <string>
#include <vector>
#include <sys/socket.h>
#include <arpa/inet.h>



#include <opencv2/opencv.hpp>

extern "C"{
    #include <stdio.h>
    #include <stdlib.h>
    #include <inttypes.h>
    #include <fcntl.h>
}

#include "../include/liborb_coproc.h"
#include "../include/libstreaming.h"

float video_framerate;
const char* server_ip_address = "192.168.254.100";
const int server_ip_port = 8080;

int main(int argc, char** argv) {

	int frames_to_capture, n_frame;
	long long total_capt_time, total_extr_time; 
	std::string frame_name;
	int exposure_time_param = 14;
	ORB_coproc_source img_source;
	uint32_t capture_duration_secs = 0;
	uint32_t img_rows, img_cols;
	cv::Mat image, image_show;
	cv::VideoCapture cap;
	std::string imagePath;

    if (argc < 5) {
        std::cerr << "USE: " << argv[0] << " <width> <height> <framerate> <exposure time parameter>" << std::endl;
        return 1;
    }

    std::cout << "Zynq Ultrascale+ 15EG" << std::endl;
    std::cout << "Video capture" << std::endl;

    char *endptr;
	img_cols = strtoul(argv[1], &endptr, 10);
	img_rows = strtoul(argv[2], &endptr, 10);
	video_framerate = (float)strtoul(argv[3], &endptr, 10);
	exposure_time_param = strtoul(argv[4], &endptr, 10);
	
	// ---------------------------------------------------------------------

	std::cout << "Video dims W: "<< img_cols << "  H: "<< img_rows << std::endl;
	img_source = CAMERA;
    ORB_coproc* coproc = ORB_coproc::get_instance(img_source, img_cols, img_rows,exposure_time_param);
    streaming client(30, CLIENT);

	image = cv::Mat(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
	coproc->capture_frame();

    uint8_t *frame_image; 
	frame_image = (uint8_t *)coproc->get_camera_frame();
	
	memcpy(image.data, frame_image, img_cols*img_rows*sizeof(uint8_t));
	cv::imwrite("image_dbg.jpg", image);
	
	client.configure_client(server_ip_address, server_ip_port);

	
	// ---------------------------------------------------------------------
	n_frame = 0;
	long long frame_time; 
	uint8_t *frame_img; 
	int sleep_time;
	std::vector<cv::Mat> image_array;
	cv::Mat image_frame(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
	std::cout << "Starting streaming to ip: " << server_ip_address << std::endl;

	// Camera matrix:
	//[[338.17202316   0.         338.42066946]
	// [  0.         338.3717479  233.90205374]
	// [  0.           0.           1.        ]]
	//
	// Distortion coefficient:
	//[[-0.42795354  0.20689643  0.00073368  0.00205363 -0.04397747]]
	//
	double fx = 338.17202316;
	double fy = 338.3717479;
	double cx = 338.42066946;
	double cy = 233.90205374;
	
	double k1 =-0.42795354;
	double k2 =0.20689643;
	double p1 =0.00073368;
	double p2 =0.00205363;
	double k3 =-0.04397747;

    cv::Mat cameraMatrix = (cv::Mat_<double>(3,3) << 
                            fx, 0, cx,
                            0, fy, cy,
                            0, 0, 1); // Ajusta fx, fy, cx, cy según tu matriz de cámara

    cv::Mat distCoeffs = (cv::Mat_<double>(5,1) << k1, k2, p1, p2, k3); // Ajusta los coeficientes de distorsión


	while(true)
	{
   		auto capture_init = std::chrono::high_resolution_clock::now();
		coproc->capture_frame();
		frame_img = (uint8_t *)coproc->get_camera_frame();
		memcpy(image_frame.data, frame_img, img_cols * img_rows * sizeof(uint8_t));
		//image_array.push_back(image_frame);

    	cv::Mat undistorted;
    	cv::undistort(image_frame, undistorted, cameraMatrix, distCoeffs);
		client.send_frame(undistorted);

	 	auto capture_end = std::chrono::high_resolution_clock::now();
		auto duracion = std::chrono::duration_cast<std::chrono::microseconds>(capture_end - capture_init);
   		frame_time = duracion.count();
		n_frame++;

		//std::cout <<  frame_time << std::endl;
		//std::cout <<  (1000000.0/video_framerate)-frame_time << std::endl;
		//std::cout <<  "--------------" << std::endl;
		sleep_time = (int)((1000000.0/video_framerate)-frame_time);
		if(sleep_time > 0){
			usleep(sleep_time);	
		}
		else{
			usleep(0);
		}
		
	}

	
	std::cout <<  "End!" << std::endl;


    return 0;
}
