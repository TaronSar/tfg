
#include <vid_emul.h>
#include <mipi_tx_ss.h> 


extern "C" {
    #include <vdma.h>
    #include <u_dma_buf.h>
}

vdma_channel_conf vdma_ch;
u_dma_buf frames_buffer;

Vid_emul::Vid_emul(){	
    u_dma_buf_setup(&frames_buffer, 0, mem_frame_buf_size);

    vdma_ch.dev_base_addr = axi_vdma_baseaddr;
	vdma_ch.direction = vdma_rd;
	vdma_ch.vdmacr = VDMA_VDMACR_CONF;
	vdma_ch.n_frame_buff = 1;
	vdma_ch.h_size = (frame_width * 2 * 2); // each pixel has 2 bytes(10 bits) and each demosaic pixel has 2 pixels in mosaic. 
    vdma_ch.v_size = frame_height;
	vdma_ch.start_addrs[0] =  (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, mem_buff_offset(0));


	vdma_reset_channel(vdma_ch);

    Mipi_tx_ss mipi_tx(mipi_tx_ss_baseaddr);

    vdma_config_channel(vdma_ch);

}


void* Vid_emul::get_frame_ptr(){

    uint8_t* frame_buff0 = (uint8_t *)u_dma_buf_get_virtual_space(frames_buffer, mem_buff_offset(0), mem_frame_size);
    
    if(frame_buff0 == NULL){
        std::cout << "ERROR: virtual space not created" << std::endl;
    }

    return frame_buff0;
}   


int Vid_emul::send_frame(){
    vdma_run_channel(vdma_ch);
	while(vdma_get_irq(vdma_ch, frmCntIrq) != 1){};
    return 0;
}   

int Vid_emul::send_frame(void* frame_ptr){
    int pic_size = frame_width * frame_height * 2 * 2;
    uint8_t* frame_buff = (uint8_t*)get_frame_ptr();
    memcpy(frame_ptr, frame_buff, pic_size);

    return send_frame();
}   


uint32_t Vid_emul::mem_buff_offset(int n_frame)
{
    if(n_frame > mem_frame_num)
    {
        std::cout << "Frame exceed the size of the memory area" << std::endl;
        return 1;
    }

    return n_frame * mem_frame_size;
}