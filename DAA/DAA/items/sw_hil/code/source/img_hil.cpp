#include <img_hil.h>
#include <opencv2/core/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/features2d/features2d.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <filesystem>
#include <thread>


void raw_frame(const cv::Mat& image, void* frame_ptr);

Img_hil::Img_hil( void* frame_ptr, int width, int height) :  frame_ptr(frame_ptr), img_width(width), img_height(height){

}

int Img_hil::get_img(const char* file_name)
{
    cv::Mat frame = cv::imread(file_name);
    if (frame.empty()) {
        std::cerr << "Could not load the image: " << file_name << std::endl;
        return 1;
    }
    int width = frame.cols; 
    int height = frame.rows;  

    
    cv::resize(frame, frame, cv::Size(img_width, img_height));
    
     
    raw_frame(frame, frame_ptr);
    return 0;
}

void rawPartialFrame(const cv::Mat& image, void* frame_ptr, int init_y, int last_y) {
    // Iterate over each pixel in the image
    int width = image.cols; 
    int yh = init_y/2;

    for (int y = init_y; y < last_y; y+=2) {
        
        for (int x = 0; x < width; x++) {
            // Get the RGB values of the pixel
            
            cv::Vec3b pixel = image.at<cv::Vec3b>(yh, x);
            
            // Pack the value in 2 bytes (10 bits for the red channel, 10 bits for the green channel)
            uint16_t pxu = (pixel[0] << 2) & 0x3FF; // Taking the blue channel for this example
            
            // Write the packed value to the binary file
            ((uint16_t*)frame_ptr)[x+(width*y)] = pxu;
            ((uint16_t*)frame_ptr)[x+(width*(y+1))] = pxu;
        }
        yh++;
    }
}

void raw_frame(const cv::Mat& image, void* frame_ptr) {
    int height = image.rows;

    // Iterate over each pixel in the image
    std::thread threadA(rawPartialFrame, image, frame_ptr, 0, (height*2)/2);
    std::thread threadB(rawPartialFrame, image, frame_ptr, (height*2)/2, (height*2));

    // Esperar a que ambos hilos terminen
    threadA.join();
    threadB.join();
}
