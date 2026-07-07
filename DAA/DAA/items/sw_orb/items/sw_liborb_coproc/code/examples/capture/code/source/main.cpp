
#include <iostream>
#include <cstdlib> // Para system()
#include <chrono>
#include <fstream>
#include <string>
#include <vector>


#include <opencv2/opencv.hpp>

extern "C"{
    #include <stdio.h>
    #include <stdlib.h>
    #include <inttypes.h>
    #include <fcntl.h>
}

#include "../include/liborb_coproc.h"

float video_framerate;

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
	cv::VideoWriter video_out;
	std::string imagePath;
	std::string cmd = "rm /run/media/nvme0n1p1/results/*";

	system(cmd.c_str());

    if (argc < 4) {
        std::cerr << "USE: " << argv[0] << " <width> <height> <seconds>" << std::endl;
        return 1;
    }

    std::cout << "Zynq Ultrascale+ 15EG" << std::endl;
    std::cout << "Video capture" << std::endl;

    char *endptr;
	img_cols = strtoul(argv[1], &endptr, 10);
	img_rows = strtoul(argv[2], &endptr, 10);
	video_framerate = (float)strtoul(argv[3], &endptr, 10);
	capture_duration_secs = strtoul(argv[4], &endptr, 10);
	exposure_time_param = strtoul(argv[5], &endptr, 10);
	
	// ---------------------------------------------------------------------

	std::cout << "Video dims W: "<< img_cols << "  H: "<< img_rows << std::endl;
	img_source = CAMERA;
    ORB_coproc* coproc = ORB_coproc::get_instance(img_source, img_cols, img_rows,exposure_time_param);
	
	video_out = cv::VideoWriter("/run/media/nvme0n1p1/results/video_out.mp4", cv::VideoWriter::fourcc('m', 'p', '4', 'v'), video_framerate, cv::Size(img_cols, img_rows));

	image = cv::Mat(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
    if (!video_out.isOpened()) {
    		std::cerr << "Error: No se pudo abrir el archivo de salida." << std::endl;
    	return -1;
    }
	coproc->capture_frame();

    uint8_t *frame_image; 
	frame_image = (uint8_t *)coproc->get_camera_frame();
	
	memcpy(image.data, frame_image, img_cols*img_rows*sizeof(uint8_t));
	cv::imwrite("image_dbg.jpg", image);
		
		
	
	// ---------------------------------------------------------------------
	n_frame = 0;
	frames_to_capture = (int)(capture_duration_secs * video_framerate);
	long long frame_time; 
	uint8_t *frame_img; 
	std::vector<cv::Mat> image_array;
	cv::Mat image_frame(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
	std::cout << "Starting to capture, frames to capture: "<<  frames_to_capture << std::endl;
	while(n_frame < frames_to_capture)
	{
   		auto capture_init = std::chrono::high_resolution_clock::now();
		coproc->capture_frame();
		frame_img = (uint8_t *)coproc->get_camera_frame();
		memcpy(image_frame.data, frame_img, img_cols * img_rows * sizeof(uint8_t));
		//image_array.push_back(image_frame);
		frame_name = "/run/media/nvme0n1p1/results/frame" + std::to_string(n_frame) + ".jpg";
		cv::imwrite(frame_name, image_frame);	

	 	auto capture_end = std::chrono::high_resolution_clock::now();
		auto duracion = std::chrono::duration_cast<std::chrono::microseconds>(capture_end - capture_init);
   		frame_time = duracion.count();
		n_frame++;

		//std::cout <<  frame_time << std::endl;
		//std::cout <<  (1000000.0/video_framerate)-frame_time << std::endl;
		//std::cout <<  "--------------" << std::endl;
		usleep((1000000.0/video_framerate)-frame_time);
		
	}
	n_frame = 0;
	std::cout <<  "Generating video" << std::endl;
	
    while(n_frame < frames_to_capture){  
		frame_name = "/run/media/nvme0n1p1/results/frame" + std::to_string(n_frame) + ".jpg";
		cv::Mat frame_video = cv::imread(frame_name, cv::IMREAD_COLOR);
		//frame_video.convertTo(frame_video, -1, 3, 0);	
		cv::imwrite(frame_name, frame_video);	
		video_out.write(frame_video);
		std::cout << (int)(((float)n_frame/(float)frames_to_capture)*100) << "%\r" ;
    	std::cout.flush();
		n_frame++;
    } 

	std::cout << std::endl;

   	video_out.release();
	
	std::cout <<  "Done!" << std::endl;


    return 0;
}
