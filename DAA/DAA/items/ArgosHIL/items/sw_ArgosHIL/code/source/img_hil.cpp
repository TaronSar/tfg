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
#include <chrono>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <linux/fb.h>
#include <unistd.h>
#include <cstring>


void raw_frame(const cv::Mat& image, void* frame_ptr);

Img_hil::Img_hil( void* frame_ptr, int width, int height, const char* fb_device, int out_w, int out_h) :  frame_ptr(frame_ptr), img_width(width), img_height(height), out_width(out_w), out_height(out_h)
{
    frame_count = 0;
    t_start = std::chrono::steady_clock::now();

    /// Open framebuffer device
    fb_fd = open(fb_device, O_RDWR);
    if (fb_fd >= 0)
    {
        /// Set output resolution if specified
        if (out_width > 0 && out_height > 0)
        {
            set_fb_resolution(out_width, out_height);
        }

        /// Query framebuffer properties
        struct fb_var_screeninfo vinfo;
        struct fb_fix_screeninfo finfo;
        ioctl(fb_fd, FBIOGET_VSCREENINFO, &vinfo);
        ioctl(fb_fd, FBIOGET_FSCREENINFO, &finfo);
        fb_width = vinfo.xres;
        fb_height = vinfo.yres;
        fb_stride = finfo.line_length;
        fb_bpp = vinfo.bits_per_pixel;
        fb_size = fb_stride * fb_height;

        /// Memory-map the framebuffer and clear it
        fb_ptr = (uint8_t*)mmap(NULL, fb_size, PROT_WRITE, MAP_SHARED, fb_fd, 0);
        if (fb_ptr == MAP_FAILED) fb_ptr = nullptr;
        else memset(fb_ptr, 0, fb_size);

        std::cout << "FB: " << fb_width << "x" << fb_height 
                  << " stride=" << fb_stride << " bpp=" << fb_bpp
                  << " R@" << vinfo.red.offset << " G@" << vinfo.green.offset 
                  << " B@" << vinfo.blue.offset << std::endl;
    }
    else
    {
        fb_ptr = nullptr;
    }
}

void Img_hil::set_fb_resolution(int w, int h)
{
    struct fb_var_screeninfo vinfo;
    if (ioctl(fb_fd, FBIOGET_VSCREENINFO, &vinfo) < 0) return;

    /// Update visible and virtual resolution
    vinfo.xres = w;
    vinfo.yres = h;
    vinfo.xres_virtual = w;
    vinfo.yres_virtual = h;

    if (ioctl(fb_fd, FBIOPUT_VSCREENINFO, &vinfo) < 0)
    {
        std::cerr << "Could not set fb resolution " << w << "x" << h << std::endl;
    }
}

int Img_hil::get_img(const char* file_name)
{
    cv::Mat frame = cv::imread(file_name);
    if (frame.empty())
    {
        std::cerr << "Could not load the image: " << file_name << std::endl;
        return 1;
    }
    
    /// 1. Send to framebuffer (DP or HDMI output)
    if (fb_ptr)
    {
        cv::Mat resized;
        /// Resize to match framebuffer dimensions if needed
        if (frame.cols != (int)fb_width || frame.rows != (int)fb_height)
        {
            cv::resize(frame, resized, cv::Size(fb_width, fb_height));
        }
        else
        {
            resized = frame;
        }

        /// Convert pixel format to match framebuffer bpp
        cv::Mat out;
        if (fb_bpp == 32)
        {
            cv::cvtColor(resized, out, cv::COLOR_BGR2BGRA);
        }
        else if (fb_bpp == 24)
        {
            out = resized;
        }
        else if (fb_bpp == 16)
        {
            cv::cvtColor(resized, out, cv::COLOR_BGR2BGR565);
        }
        
        /// Copy scanlines to framebuffer using stride-aligned offsets
        int copy_w = std::min(out.cols, (int)fb_width);
        int copy_h = std::min(out.rows, (int)fb_height);
        int dst_line_bytes = copy_w * (fb_bpp / 8);
        
        for (int y = 0; y < copy_h; y++)
        {
            memcpy(fb_ptr + y * fb_stride, out.ptr(y), dst_line_bytes);
        }
    }

    /// 2. Resize for VDMA/MIPI output path
    cv::resize(frame, frame, cv::Size(img_width, img_height));
     
    /// 3. Pack and send to VDMA buffer
    raw_frame(frame, frame_ptr);
    
    /// FPS counter (prints once per second)
    frame_count++;
    auto now = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(now - t_start).count();
    if (elapsed >= 1.0)
    {
        std::cout << "FPS: " << frame_count / elapsed << std::endl;
        frame_count = 0;
        t_start = now;
    }
    
    return 0;
}

void rawPartialFrame(const cv::Mat& image, void* frame_ptr, int init_y, int last_y)
{
    int width = image.cols; 
    int yh = init_y/2;

    /// Process pixel rows in pairs (mosaic duplication)
    for (int y = init_y; y < last_y; y+=2)
    {
        for (int x = 0; x < width; x++)
        {
            cv::Vec3b pixel = image.at<cv::Vec3b>(yh, x);
            
            /// Pack blue channel into 10-bit value (left-shifted by 2)
            uint16_t pxu = (pixel[0] << 2) & 0x3FF;
            
            /// Write same value to both mosaic rows
            ((uint16_t*)frame_ptr)[x+(width*y)] = pxu;
            ((uint16_t*)frame_ptr)[x+(width*(y+1))] = pxu;
        }
        yh++;
    }
}

void raw_frame(const cv::Mat& image, void* frame_ptr)
{
    int height = image.rows;

    /// Split frame processing across two threads for throughput
    std::thread threadA(rawPartialFrame, image, frame_ptr, 0, (height*2)/2);
    std::thread threadB(rawPartialFrame, image, frame_ptr, (height*2)/2, (height*2));

    /// Wait for both threads to finish
    threadA.join();
    threadB.join();
}
