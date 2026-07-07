/**
 * @file main.c
 * @brief main code
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */


#include <stdlib.h>
#include <fcntl.h>
#include <stdio.h>
#include <math.h>
#include <time.h>
#include <unistd.h>

#include <string.h>
#include <stdint.h>
#include <linux/ioctl.h>
#include <errno.h>
#include <dlfcn.h>


#include "xv_demosaic.h"
#include "xv_gamma_lut.h"

#include "dbg.h"
#include "memmap.h"
#include "gpio.h"
#include "axi_gpio.h"
#include "imx296.h"
#include "img.h"
#include "vdma.h"
#include "dma.h"
#include "u_dma_buf.h"
#include "v_proc_ss.h"

#define KB(x)	x * 1024
#define MB(x)   x * 1024 * 1024

#define V_PROC_SS_BASE_ADDR		0xB0000000U

#define FRAMES_BUFF_SIZE		MB(64) 	// 64MB
#define FRAMES_NUM				32U 	// 2MB each frame
#define FRAME_SIZE				(FRAMES_BUFF_SIZE / FRAMES_NUM)  		
#define	FRAME_OFFSET(x)			(x * FRAME_SIZE)

#define GAMMA_VAL				1.2
#define PIXEL_N_BYTES			1U	

// For other resolutions try this (is an aproximation) -> ceil(((80*1024U)/(cam_conf.width*PIXEL_N_BYTES))); 
#define NON_VALID_ROWS			28U //-> valid for 640x480; 16U -> valid for 1280x960


#define SOURCE_HEIGHT  			1440
#define SOURCE_WIDTH   			1080
			
#define RESCALED_HEIGHT  		480U
#define RESCALED_WIDTH   		640U

#define DEV_VDMA_CAM_BASE_ADDR	0xB0030000U

#define DEV_DMA_CFG_BASE_ADDR	0xA0000000U
#define DEV_DMA_CFG_SIZE		0x40U
#define DEV_DMA_DATA_BASE_ADDR	0xA0010000U
#define DEV_DMA_DATA_RD_SIZE	(uint32_t)RESCALED_HEIGHT*RESCALED_WIDTH	// 640*480
#define DEV_DMA_DATA_WR_SIZE	0x01000000U // This value have to be large enough for received max. expected bytes

#define DEV_DMA_ADQ_BASE_ADDR	0x80010000U
#define DEV_DMA_ADQ_SIZE		DEV_DMA_CFG_SIZE

#define PRE_ORB_HEIGHT  		RESCALED_HEIGHT
#define PRE_ORB_WIDTH   		RESCALED_WIDTH

#define DEV_AXI_GPIO_BASE_ADDR	0xB0060000U

#define FAST_FRAME_PIXS			0U// 3 -> 1.2   2 -> 3.58
#define NEW_FAST_DIMS(x)		x + FAST_FRAME_PIXS
#define FAST_THRESHOLD			7
#define N_SCALES				7

void printReg(uint32_t addr){
	uint32_t reg;

	memmap_init(mm, addr);

	memmap_read(mm, addr, &reg);

	memmap_close(mm);

	print("Register Addr: 0x%08X, val: 0x%08X\n", addr, reg);
}

void setReg(uint32_t addr, uint32_t reg){

	memmap_init(mm, addr);

	memmap_write(mm, addr, reg);

	memmap_close(mm);

}

void demosaic_config(uint32_t vid_width, uint32_t vid_height, uint8_t bayer_phase){
	XV_demosaic cfa;
    // DEMOSAIC CONFIGURATION
    XV_demosaic_Initialize(&cfa, XPAR_V_DEMOSAIC_0_DEVICE_ID);
	XV_demosaic_Set_HwReg_width(&cfa, vid_width);
	XV_demosaic_Set_HwReg_height(&cfa, vid_height);
	XV_demosaic_Set_HwReg_bayer_phase(&cfa, bayer_phase); // Check Bayer Phase 
	XV_demosaic_EnableAutoRestart(&cfa);
	XV_demosaic_Start(&cfa);
}

void gamma_config(uint32_t vid_width, uint32_t vid_height, uint8_t data_width){
	XV_gamma_lut gamma_inst;
	uint16_t* gamma_reg;
	gamma_reg = (uint16_t*)malloc((1<<data_width) * sizeof(uint16_t));
	int i;
	float gamma_val = GAMMA_VAL;
    // GAMMA LUT CONFIGURATION
	//------------ Gamma calc
	for(i = 0; i<(1<<data_width); i++){
		gamma_reg[i] = (pow((i / (float)(1<<data_width)), (1/gamma_val)) * (float)(1<<data_width));
	}
	//----------
	XV_gamma_lut_Initialize(&gamma_inst, XPAR_V_GAMMA_LUT_0_DEVICE_ID);
	XV_gamma_lut_Set_HwReg_width(&gamma_inst,vid_width);
	XV_gamma_lut_Set_HwReg_height(&gamma_inst, vid_height);
	XV_gamma_lut_Set_HwReg_video_format(&gamma_inst, 0x00);
	XV_gamma_lut_Write_HwReg_gamma_lut_0_Bytes(&gamma_inst, 0,(char *) gamma_reg, (2<<data_width));
	
	XV_gamma_lut_Write_HwReg_gamma_lut_1_Bytes(&gamma_inst, 0,(char *) gamma_reg, (2<<data_width));
	XV_gamma_lut_Write_HwReg_gamma_lut_2_Bytes(&gamma_inst, 0,(char *) gamma_reg, (2<<data_width));

	XV_gamma_lut_Start(&gamma_inst);
	XV_gamma_lut_EnableAutoRestart(&gamma_inst);

}


uint8_t file_data_dump(const char* fname, uint32_t frame[], uint32_t words){

    uint32_t i, data;


    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }
		
	for(i = 0; i < words; i++){
		data = frame[i];

    	fprintf(file, "%08X",data);
		fprintf(file, "\n");
		
	}
	
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}


int main(){
	uint32_t i; 
	clock_t begin, end;
	float time_spent;
	float rsz_scale;
	float inv_rsz_scale;


	v_proc_ss_conf v_proc_ss_config;

	dma_channel_conf dma_ch_data_wr;
	dma_channel_conf dma_ch_data_rd;
	dma_channel_conf dma_ch_cfg;
	dma_channel_conf dma_ch_adq;

	axi_gpio_conf reset_pin_cfg;

	uint8_t n_scales = N_SCALES;
	float scales_list[N_SCALES+1] = { 1.0, 1.2, 1.73, 2.01, 2.48, 2.98, 3.58};//, 4.29}; //Error found with 4.29


	
	vdma_channel_conf vdma_ch_cam;

	uint32_t frameBuffAddrs;

	imx296_conf cam_conf;
	u_dma_buf frames_buffer;

	cam_conf.width = SOURCE_WIDTH;
	cam_conf.height = SOURCE_HEIGHT;
	cam_conf.bayer_phase = IMX296_BAYER_PHASE;

	// Frame non valid (transmission information) bytes calculation 

	v_proc_ss_config.dev_base_addr = V_PROC_SS_BASE_ADDR;
	v_proc_ss_config.width = SOURCE_WIDTH;
	v_proc_ss_config.height = SOURCE_HEIGHT;
	v_proc_ss_config.data_width = 8;//bits
	

    print("------- AXU15EG IMX296 -------\n");
    print("-- Included Resize --\n");
    print("-- Included FAST --\n");
    print("-- Included Brief --\n\n");

	u_dma_buf_setup(&frames_buffer, 0, FRAMES_BUFF_SIZE);

	frameBuffAddrs = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(0));

	v_proc_ss_setup(v_proc_ss_config);


    // POWER UP CAMERA
    print("** POWER UP CAMERA **\n");

	gpio_init(MIPI_A_PWUP, OUTPUT);
//
	gpio_set(MIPI_A_PWUP, LOW);
	usleep(1000000);
	gpio_set(MIPI_A_PWUP, HIGH);
	usleep(500000);

    print("\n** NO DMA CONFIGURATION **\n");
	dma_ch_adq.dev_base_addr = DEV_DMA_ADQ_BASE_ADDR;
	dma_ch_adq.direction = dma_rd;
	dma_ch_adq.irqs = DMA_DMASR_IOC_IRQ;
	dma_ch_adq.length = DEV_DMA_ADQ_SIZE;
	dma_ch_adq.target_addr = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)+ (FRAME_SIZE / 2));

	dma_ch_cfg.dev_base_addr = DEV_DMA_CFG_BASE_ADDR;
	dma_ch_cfg.direction = dma_rd;
	dma_ch_cfg.irqs = DMA_DMASR_IOC_IRQ;
	dma_ch_cfg.length = DEV_DMA_CFG_SIZE;
	dma_ch_cfg.target_addr = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3));

	dma_ch_cfg.dev_base_addr = DEV_DMA_CFG_BASE_ADDR;
	dma_ch_cfg.direction = dma_rd;
	dma_ch_cfg.irqs = DMA_DMASR_IOC_IRQ;
	dma_ch_cfg.length = DEV_DMA_CFG_SIZE;
	dma_ch_cfg.target_addr = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3));


	dma_ch_data_rd.dev_base_addr = DEV_DMA_DATA_BASE_ADDR;
	dma_ch_data_rd.direction = dma_rd;
	dma_ch_data_rd.irqs = 0U;
	dma_ch_data_rd.length = DEV_DMA_DATA_RD_SIZE;
	dma_ch_data_rd.target_addr = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(4));

	dma_ch_data_wr.dev_base_addr = DEV_DMA_DATA_BASE_ADDR;
	dma_ch_data_wr.direction = dma_wr;
	dma_ch_data_wr.irqs = 0U;
	dma_ch_data_wr.length = DEV_DMA_DATA_WR_SIZE;
	dma_ch_data_wr.target_addr = (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(5));
	
	dma_reset_core(dma_ch_adq);
	dma_reset_core(dma_ch_cfg);
	dma_reset_core(dma_ch_data_rd);
///
	dma_config_channel(dma_ch_adq);
	dma_config_channel(dma_ch_cfg);
	dma_config_channel(dma_ch_data_rd);
	dma_config_channel(dma_ch_data_wr);
	
    // VDMA CONFIGURATION
    print("\n** VDMA CONFIGURATION **\n");

	vdma_ch_cam.dev_base_addr = DEV_VDMA_CAM_BASE_ADDR;
	vdma_ch_cam.direction = vdma_wr;
	vdma_ch_cam.vdmacr = VDMA_VDMACR_CONF;
	vdma_ch_cam.start_addrs[0] = frameBuffAddrs;
	vdma_ch_cam.n_frame_buff = 1;
	vdma_ch_cam.h_size = RESCALED_WIDTH;
	vdma_ch_cam.v_size = RESCALED_HEIGHT;
//
	vdma_reset_channel(vdma_ch_cam);
	vdma_config_channel(vdma_ch_cam);


  	print("\n** DEMOSAIC & GAMMA CONFIGURATION **\n");
	demosaic_config(cam_conf.width, cam_conf.height, cam_conf.bayer_phase);
	gamma_config(cam_conf.width, cam_conf.height, 8);

    print("\n** CONFIGURE IMX296 **\n");

	if(imx296_setup(cam_conf) != 0)
	{
		print("Error configuring IMX296\n");
		gpio_set(MIPI_A_PWUP, LOW);
		return 1;
	}


	reset_pin_cfg.dev_base_addr = DEV_AXI_GPIO_BASE_ADDR;
	reset_pin_cfg.port = AXI_GPIO;


	usleep(2000000);

    print("\n** START VDMA **\n");
	
	rsz_scale = 2.25;
	inv_rsz_scale = 1.0 / rsz_scale;

	setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3) + (FRAME_SIZE / 2)), SOURCE_WIDTH);
	setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3) + (FRAME_SIZE / 2)) + 4U, SOURCE_HEIGHT);
	setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3) + (FRAME_SIZE / 2)) + 8U, (uint32_t)(rsz_scale * (1 << 14U)));
	setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3) + (FRAME_SIZE / 2)) + 12U, (uint32_t)(inv_rsz_scale * (1 << 14U)));
	
	dma_run_channel(dma_ch_adq);
	dma_wait_idle(dma_ch_adq);
	
	for(i = 0; i < 1; i++){
		print("frame %d\n",i);
		vdma_run_channel(vdma_ch_cam);
		while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1);
	}
	
	
	print("frame A\n");
	begin = clock();   
	vdma_update_frame_addr(vdma_ch_cam, (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(1)));
	vdma_run_channel(vdma_ch_cam);
	while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1);
  	uint32_t* testPointer = u_dma_buf_get_virtual_space(frames_buffer, (uint32_t)FRAME_OFFSET(1), RESCALED_WIDTH * RESCALED_HEIGHT);
	end = clock();
	time_spent = (double)(end - begin); //in microseconds
    print("Time spent: %f ms\n", time_spent / 1000.0);
	img_create_gray8_2pxclk("testA.ppm", (uint64_t *)testPointer, RESCALED_WIDTH, RESCALED_HEIGHT);
////	
	for(i = 0; i < 1; i++){
		print("frameB %d\n",i);
		begin = clock();   
		vdma_update_frame_addr(vdma_ch_cam, (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(4)));
		vdma_run_channel(vdma_ch_cam);
		while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1);
  		uint32_t* testPointerB = u_dma_buf_get_virtual_space(frames_buffer, (uint32_t)FRAME_OFFSET(4), RESCALED_WIDTH * RESCALED_HEIGHT);	
		end = clock();
    	print("Captured pictures\n");
		time_spent = (double)(end - begin); //in microseconds
    	print("Time spent: %f ms\n", time_spent / 1000.0);
        char fileName[20];
        sprintf(fileName, "testB%d.ppm", i);
		img_create_gray8_2pxclk(fileName, (uint64_t *)testPointerB, RESCALED_WIDTH, RESCALED_HEIGHT);
	}
return 0;
	
	// ------------------ IMAGES FILES CONVERSION -------------------
    print("\n*** ORB-SLAM ***\n");
    print("** image conversion **\n");
  	uint8_t* testpreORB = u_dma_buf_get_virtual_space(frames_buffer, (uint32_t)FRAME_OFFSET(4), RESCALED_WIDTH * RESCALED_HEIGHT);


	//-------------------- TRANSMISSION WITH ORB --------------------
	uint32_t new_height, new_width;
	uint32_t n_kps = 0;
	
	for(i = 0; i < n_scales; i++){

		axi_gpio_set_pin(reset_pin_cfg, 0U);
		usleep(500);
		axi_gpio_clear_pin(reset_pin_cfg, 0U);

		new_width = (uint32_t)(((float)RESCALED_WIDTH)/scales_list[i]);
		new_height = (uint32_t)(((float)RESCALED_HEIGHT)/scales_list[i]);
		
		img_create_gray8("testpreORB.ppm", (uint8_t *)testpreORB, RESCALED_WIDTH, RESCALED_HEIGHT);	

		rsz_scale = scales_list[i];
		inv_rsz_scale = 1.0 / rsz_scale;
    	print("\nORB extraction started Scale: %f\n", scales_list[i]);

		begin = clock();   

		setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)), PRE_ORB_WIDTH);
		setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)) + 4U, PRE_ORB_HEIGHT);
		setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)) + 8U, (uint32_t)(rsz_scale * (1 << 14U)));
		setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)) + 12U, (uint32_t)(inv_rsz_scale * (1 << 14U)));
		setReg((uint32_t)u_dma_buf_get_physical_addr(frames_buffer, (uint32_t)FRAME_OFFSET(3)) + 16U, (uint32_t)(FAST_THRESHOLD));
		

		dma_run_channel(dma_ch_cfg);
		dma_wait_idle(dma_ch_cfg);

		dma_run_channel(dma_ch_data_rd);
		dma_run_channel(dma_ch_data_wr);
		dma_wait_idle(dma_ch_data_rd);
		dma_wait_idle(dma_ch_data_wr);

		end = clock();
		time_spent = (double)(end - begin); //in microseconds
    	print("ORB extraction COMPLETED! new width: %d, new height: %d\n", new_width, new_height);
    	print("Time spent: %f ms\n", time_spent / 1000.0);
		print("data received: %d Bytes\n",(dma_get_length(dma_ch_data_wr)));
		print("Kp received: %d \n",(dma_get_length(dma_ch_data_wr)/64));
		n_kps += (dma_get_length(dma_ch_data_wr)/64);
		uint32_t* testpostORB = u_dma_buf_get_virtual_space(frames_buffer, (uint32_t)FRAME_OFFSET(5), (dma_get_length(dma_ch_data_wr)));	
		//img_create_gray8("testORB.ppm", (uint8_t*)testpostORB, new_width, new_height);
		
		file_data_dump("testdata.txt",testpostORB, (dma_get_length(dma_ch_data_wr)/4U));

	}

		print("Frame kps: %d (FAST Threshold: %d)\n",n_kps, (uint32_t)FAST_THRESHOLD);

    return 0;
}
  