
#ifndef IMG_HIL_H
#define IMG_HIL_H

#include <stdio.h>
#include <stdint.h>

class Img_hil{

public:
    Img_hil( void* frame_ptr, int width, int height);

    int get_img(const char* file_name);

private:
    int img_width;
    int img_height;
    void* frame_ptr;

};

#endif