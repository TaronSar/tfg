
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

#define FPS		5//Hz

#include "../include/liborb_coproc.h"

typedef struct {
	int score;
	int angle;
    int col;
	int row;
	int octave;
	int desc[8];
} keypoint;


int main(int argc, char** argv) {

	const uint8_t fast_threshold = 20U;
	int frames_to_capture;
	long long total_capt_time, total_extr_time; 
	std::string frame_name;
	int n_scales = 7, n_kp_frame = 0, n_frame = 0;
	//float scales[8] = {1.0, 1.2, 1.44, 1.728, 2.0736, 2.488, 2.9859};// 4.29};
	float scales[8] = {1.0, 1.2, 1.73, 2.01, 2.48, 2.98, 3.58};// 4.29};
	float current_scale;
	int j, i;
	std::vector<keypoint> kps;
	int kp_size[8];
	int new_row, new_col;
	uint32_t n_data;
	ORB_coproc_source img_source;
	
	uint32_t img_rows, img_cols, frameIndex;
	cv::Mat image, image_show;
	cv::VideoCapture cap;
	cv::VideoWriter video_out;
	std::string imagePath;
	std::string cmd = "rm results/*";
   	std::ofstream out_file("output.txt");

	system(cmd.c_str());

    if (!out_file.is_open()) {
        std::cerr << "Error opening txt file" << std::endl;
        return 1;
    }

    if (argc < 3) {
        std::cerr << "USE: " << argv[0] << " <image route> or camera <width> <height>" << std::endl;
        return 1;
    }


    std::cout << "Zynq Ultrascale+ 15EG" << std::endl;
    std::cout << "ORB Coprocessors" << std::endl;

	if (strcmp(argv[1], "image") == 0 && argc == 3) 
	{
		imagePath = argv[2];
    	image = cv::imread(imagePath, cv::IMREAD_GRAYSCALE);
	
    	if (image.empty()) {
    	    std::cerr << "The image cannot be loaded: " << imagePath << std::endl;
    	    return 1;
    	}   	

		cv::imwrite("image_gray.jpg", image);

		img_cols = image.cols;
		img_rows = image.rows;

		img_source = IMAGE;
    	std::cerr << "Local image!"<< std::endl;

    }
	else if(strcmp(argv[1], "video") == 0 && argc == 3)
	{
		std::string videoPath = argv[2];
    	cap = cv::VideoCapture(videoPath);
	//
    	if (!cap.isOpened()) {
    	    std::cerr << std::endl << "Could not open video feed." << std::endl;
    	    return -1;
    	}
//
		img_cols = cap.get(cv::CAP_PROP_FRAME_WIDTH);
		img_rows = cap.get(cv::CAP_PROP_FRAME_HEIGHT);
//
		img_source = VIDEO;
    	std::cerr << "Local video!"<< std::endl;
	}
	else if(strcmp(argv[1], "camera") == 0 && argc == 4)
	{
		img_source = CAMERA;
		
    	std::cerr << "Camera!"<< std::endl;
    	char *endptr;
		img_cols = strtoul(argv[2], &endptr, 10);
		img_rows = strtoul(argv[3], &endptr, 10);
	}
	else
	{

    	std::cerr << "Camera dimensions not set"<< std::endl;
		return 1;
	}

	// ---------------------------------------------------------------------

	std::cout << "Image dims W: "<< img_cols << "  H: "<< img_rows << std::endl;

    ORB_coproc* coproc = ORB_coproc::get_instance(img_source, img_cols, img_rows);

	if(coproc->get_source() == CAMERA){		
		video_out = cv::VideoWriter("results/video_out.mp4", cv::VideoWriter::fourcc('m', 'p', '4', 'v'), FPS, cv::Size(img_cols, img_rows));
		image = cv::Mat(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
    	if (!video_out.isOpened()) {
        		std::cerr << "Error: No se pudo abrir el archivo de salida." << std::endl;
        	return -1;
    	}
		coproc->capture_frame();

			std::cout << "out " << std::endl;
        uint8_t *frame_img; 
		frame_img = (uint8_t *)coproc->get_camera_frame();
		
		memcpy(image.data, frame_img, img_cols*img_rows*sizeof(uint8_t));
		cv::imwrite("image_dbg.jpg", image);
		

	}
	else if(coproc->get_source() == IMAGE){

    	image = cv::imread(imagePath, cv::IMREAD_GRAYSCALE);
		void *input_frame = coproc->get_coproc_in_frame(); 
		memcpy(input_frame, image.data, img_cols*img_rows*sizeof(uint8_t));
		//image.convertTo(image, -1, 3, 0);
		cv::cvtColor(image, image_show, cv::COLOR_GRAY2BGR);

	}
	else if(coproc->get_source() == VIDEO){	
		video_out = cv::VideoWriter("results/video_out.mp4", cv::VideoWriter::fourcc('m', 'p', '4', 'v'), FPS, cv::Size(img_cols, img_rows));
		image = cv::Mat(img_rows, img_cols, CV_8UC1, cv::Scalar(0));
    	if (!video_out.isOpened()) {
        		std::cerr << "Error: No se pudo abrir el archivo de salida." << std::endl;
        	return -1;
    	}

	}
	// ---------------------------------------------------------------------
	frameIndex = 0;
	n_frame = 0;
	total_capt_time = 0;
	total_extr_time = 0;
	frames_to_capture = 50;
	while(n_frame < frames_to_capture)
	{
		long long capt_time, extr_time; 
		n_kp_frame = 0;
		if(coproc->get_source() == CAMERA){
			std::cout << "Camera " << std::endl;
   			auto capture_init = std::chrono::high_resolution_clock::now();
			coproc->capture_frame();
	 		auto capture_end = std::chrono::high_resolution_clock::now();
			auto duracion = std::chrono::duration_cast<std::chrono::microseconds>(capture_end - capture_init);
   			capt_time = duracion.count();

			uint8_t *frame_img; 
			void *input_frame = coproc->get_coproc_in_frame(); 
			
			frame_img = (uint8_t *)coproc->get_camera_frame();
			memcpy(input_frame, frame_img, img_cols * img_rows * sizeof(uint8_t));
			memcpy(image.data, frame_img, img_cols * img_rows * sizeof(uint8_t));
			image.convertTo(image, -1, 3, 0);
			cv::cvtColor(image, image_show, cv::COLOR_GRAY2BGR);
		}
		else if(coproc->get_source() == VIDEO){
			
			cv::Mat frame;
        	cap >> frame;
			cv::cvtColor(frame, image, cv::COLOR_BGR2GRAY);
			cv::cvtColor(image, image_show, cv::COLOR_GRAY2BGR);

			void *input_frame = coproc->get_coproc_in_frame(); 
			memcpy(input_frame, image.data, img_cols*img_rows*sizeof(uint8_t));
		}
		extr_time = 0;
    	cv::Mat frame_show = image_show.clone();
		for(j = 0; j < n_scales; j++){
			
			current_scale = scales[j];

	 		auto extraction_init = std::chrono::high_resolution_clock::now();
			coproc->update_frame(j);
			coproc->config(current_scale, fast_threshold);
			n_data = coproc->run();
	 		auto extraction_end = std::chrono::high_resolution_clock::now();
		
			auto duracion = std::chrono::duration_cast<std::chrono::microseconds>(extraction_end - extraction_init);
   			extr_time += duracion.count();
			//std::cout << "Scale: " << current_scale << std::endl;
			//std::cout << "Bytes received: " << n_data << std::endl;
			//std::cout << "Kp received: " << (n_data/64) << std::endl;
			kp_size[j] = (n_data/64);
			n_kp_frame += (n_data/64);
		}
		uint32_t* results;
		for(j = 0; j < n_scales; j++){
			current_scale = scales[j];
    		cv::Mat scale_show = image_show.clone();
			results = (uint32_t *)coproc->get_results(j);
			for(i = 0; i < kp_size[j]; i++){
				keypoint kPoint;
				kPoint.octave = scales[j];
				kPoint.score = (results[i*16] & 0x7F);
				kPoint.angle = (results[i*16] >> 7 & 0x1FF);
				kPoint.row = (results[i*16] >> 16 & 0x1FF);
				kPoint.col = ((results[i*16] >> 25 & 0x7F) | ((results[i*16+1] & 0xFU) << 7));
				for(int k = 0; k < 8; k++){
					kPoint.desc[j] = (int)((results[(i*16)+k+1] >> 4U) | ((results[(i*16)+(2+k)] & 0xFU) << 28U) );
				}
				new_col = (int)(((float)kPoint.col*current_scale));
				new_row = (int)(((float)kPoint.row*current_scale));
				kps.push_back(kPoint);
    			cv::Point keypoint(new_col, new_row);
				cv::circle(scale_show, keypoint, 2, cv::Scalar(0,0,255), 1);
				cv::circle(frame_show, keypoint, 2, cv::Scalar(0,0,255), 1);
			
			}
			//frame_name = "results/frame" + std::to_string(n_frame) +"-"+std::to_string(current_scale)+ ".jpg";
			//cv::imwrite(frame_name, scale_show);
			
		}
		frame_name = "results/frame" + std::to_string(n_frame) + ".jpg";
		cv::imwrite(frame_name, frame_show);	
		std::cout << std::endl;
		
		std::cout <<"Frame " << n_frame << " keypoints: " << n_kp_frame  << std::endl;
   		std::cout << "Capture time: " << capt_time << " us Extraction time: " << extr_time << " us" << std::endl;
		std::cout << std::endl;
		total_capt_time += capt_time;
		total_extr_time += extr_time;
		//frame_name = "results/frame" + std::to_string(n_frame) + ".jpg";
		//cv::imwrite(frame_name, image_show);

		if(coproc->get_source() == CAMERA){
			video_out.write(frame_show);
			n_frame++;

			out_file.close();			
			usleep(60000);
		}
		else if(coproc->get_source() == VIDEO){
			video_out.write(image_show);
			n_frame++;

			usleep(60000);
		}
		else{
    		out_file.close();
			break;
		}

	}
	if(coproc->get_source() == CAMERA){
   		video_out.release();
	}
	

	std::cout << "Keypoints (avg): "<< kps.size()/50  << std::endl;
   	std::cout << "Capture time (avg): " << (total_capt_time/frames_to_capture) << " us\nExtraction time: " << (total_extr_time/frames_to_capture) << " us" << std::endl;
	std::cout << "ORB extractor (avg): " << ((total_capt_time+total_extr_time)/frames_to_capture) << " us" << std::endl;
	std::cout << std::endl;

    return 0;
}
