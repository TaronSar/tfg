
#ifndef VID_EMU_H
#define VID_EMU_H

#include <iostream>
#include <cstring>
#include <stdio.h>
#include <stdint.h> 

class Vid_emul{

public:
    Vid_emul();

    void* get_frame_ptr();
    int send_frame();
    int send_frame(void* frame_ptr);

private:

    const uint32_t mipi_tx_ss_baseaddr = 0xA0000000;
    const uint32_t axi_vdma_baseaddr = 0xA0010000;
    
    const int frame_width = 1280;
    const int frame_height = 980;

    const int mem_frame_buf_size = 64 * 1024 * 1024; // 64MB
    const int mem_frame_num = 4;
    const int mem_frame_size = mem_frame_buf_size/mem_frame_num;

    uint32_t mem_buff_offset(int n_frame);
};

#endif