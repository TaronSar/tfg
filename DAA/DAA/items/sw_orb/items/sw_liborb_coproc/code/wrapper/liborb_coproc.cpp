/**
 * @file orb_coproc.cpp
 * @brief Wrapper to ORB coprocessor execution.
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */

extern "C"{
    #include <stdio.h>
    #include <stdlib.h>

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

}

// Linux exceptions
#include <iostream>
#include <stdexcept>
//
#include <mutex>
#include "liborb_coproc.h"

const uint32_t bits_color_depth			= 8U;
const float gamma_value					= 1.2;
const uint32_t u_dma_buf_size 			= 64U * 1024U * 1024U;
const uint32_t n_frames 				= 16;
const uint32_t u_dma_buf_id 			= 0U;
const uint32_t axi_gpio_base_addr 		= 0xB0060000U;
const uint32_t v_proc_ss_base_addr 		= 0xB0000000U;
const uint32_t vdma_data_base_addr 		= 0xB0030000U;
const uint32_t dma_adq_base_addr 		= 0xB0070000U; //0x80010000U
const uint32_t dma_conf_base_addr 		= 0xA0000000U;
const uint32_t dma_data_base_addr 		= 0xA0010000U;
const uint32_t version_reg_addr 		= 0xA00201FCU;
const uint32_t dma_adq_size 		    = 0x40U;
const uint32_t dma_conf_size 		    = 0x40U;
const uint32_t dma_data_s2mm_size	    = 0x01000000U;

const uint32_t non_valid_rows			= 10U;
const uint32_t bytes_per_pixel			= 1U;	
// crop for 1280x980 sensor ROI
const uint32_t video_crop_left			= 88U; 
const uint32_t video_crop_top			= 54U;
const uint32_t video_source_width		= 1280U; 
const uint32_t video_source_height  	= 980U;
const uint32_t powup_waiting_time_camera = 500000U; //us


typedef enum {
    none = 0,
    camera_frame = 1,
    copr_conf = 2,
    copr_data_in = 4,
    adq_conf = 5,
    copr_data_out = 6
} frame_type;

int ORB_coproc::fast_th = 0;
int ORB_coproc::last_matches = 0;
int ORB_coproc::actu_matches = 0;
bool ORB_coproc::is_ini = false;

uint32_t ORB_coproc::img_height = 0;
uint32_t ORB_coproc::img_width = 0;
uint32_t ORB_coproc::shs = 0;
uint16_t ORB_coproc::gain = 0;
bool ORB_coproc::camera = false;
bool ORB_coproc::initialized = false;
void* ORB_coproc::frame = 0;
uint32_t ORB_coproc::mipi_a_pwup = 0;
std::mutex ORB_coproc::mtx;

void printReg(uint32_t addr){
	uint32_t reg;

    mem_map mm;
	memmap_init(&mm, addr);

	memmap_read(mm, addr, &reg);

	memmap_close(mm);

	print("[COPROC] Register Addr: 0x%08X, val: 0x%08X\n", addr, reg);
}

uint32_t get_version();
uint32_t get_frame_addr(frame_type n_frame);
void* get_frame_array(frame_type n_frame);
void setReg(uint32_t addr, uint32_t reg);
void reset_coproc();
void demosaic_config(uint32_t vid_width, uint32_t vid_height, uint8_t bayer_phase);
void gamma_config(uint32_t vid_width, uint32_t vid_height, uint8_t data_width,  float gamma_value);

static vdma_channel_conf vdma_ch_cam;
static dma_channel_conf dma_ch_adq;
static dma_channel_conf dma_ch_cfg;
static dma_channel_conf dma_ch_data_rd;
static dma_channel_conf dma_ch_data_wr;
static axi_gpio_conf reset_pin_cfg;
static u_dma_buf frames_buffer;
static v_proc_ss_conf v_proc_ss_config;

static float adq_rescale_factor;
static uint32_t non_valid_bytes;

ORB_coproc* ORB_coproc::singleton= nullptr;
static void* virtual_spaces[u_dma_buf_size  / n_frames];

// Constructor implementation
ORB_coproc::ORB_coproc(uint32_t img_width, uint32_t img_height, uint32_t shs, uint16_t gain, bool camera)  
{

	print("[COPROC] Version: %d\n", get_version());
	u_dma_buf_setup(&frames_buffer, u_dma_buf_id, u_dma_buf_size);

	// Virtual spaces initialization
	for(int vs = 0; vs < u_dma_buf_size  / n_frames; vs++){
		virtual_spaces[vs] = NULL;
	}

	if(camera)
	{
		imx296_conf cam_conf;
		uint32_t conf_mem[4]; 

		cam_conf.crop_left = video_crop_left;
		cam_conf.crop_top = video_crop_top;
		cam_conf.width = video_source_width;
		cam_conf.height = video_source_height;
		cam_conf.bayer_phase = IMX296_BAYER_PHASE;
		cam_conf.shs = shs;
		cam_conf.gain = gain;

		int ret = read_gpio_xtrig(&mipi_a_pwup);
		if (ret != 0)
		{
			print("[COPROC] Error configuring MIPI PWUP GPIO\n");
		}
		gpio_init(mipi_a_pwup, OUTPUT);
//
		gpio_set(mipi_a_pwup, LOW);
		usleep(powup_waiting_time_camera);
		gpio_set(mipi_a_pwup, HIGH);
		usleep(powup_waiting_time_camera);

		v_proc_ss_config.dev_base_addr = v_proc_ss_base_addr;
		v_proc_ss_config.width = cam_conf.width;
		v_proc_ss_config.height = cam_conf.height;
		v_proc_ss_config.data_width = 8;//bits

		v_proc_ss_setup(v_proc_ss_config);

		// CONFIGURATION ADQUISITION DMA 
		dma_ch_adq.dev_base_addr = dma_adq_base_addr;
		dma_ch_adq.direction = dma_rd;
		dma_ch_adq.irqs = DMA_DMASR_IOC_IRQ;
		dma_ch_adq.length = dma_adq_size;
		dma_ch_adq.target_addr = get_frame_addr(adq_conf);
		dma_reset_core(dma_ch_adq);
		dma_config_channel(dma_ch_adq);

		vdma_ch_cam.dev_base_addr = vdma_data_base_addr;
		vdma_ch_cam.direction = vdma_wr;
		vdma_ch_cam.vdmacr = VDMA_VDMACR_CONF;
		vdma_ch_cam.start_addrs[0] = get_frame_addr(none);
		vdma_ch_cam.n_frame_buff = 1;
		vdma_ch_cam.h_size = img_width;
		vdma_ch_cam.v_size = img_height + non_valid_rows;
//
		vdma_reset_channel(vdma_ch_cam);
		vdma_config_channel(vdma_ch_cam);

		demosaic_config(cam_conf.width, cam_conf.height, cam_conf.bayer_phase);
		gamma_config(cam_conf.width, cam_conf.height, bits_color_depth, gamma_value);

		adq_rescale_factor = (cam_conf.width / (float)img_width);

		float inv_scale = 1.0 / adq_rescale_factor;
		conf_mem[0] = cam_conf.width;
		conf_mem[1] = cam_conf.height;
		conf_mem[2] = (uint32_t)(adq_rescale_factor * (1 << 14U));
		conf_mem[3] = (uint32_t)(inv_scale * (1 << 14U));

		setReg(get_frame_addr(adq_conf), conf_mem[0]);
		setReg(get_frame_addr(adq_conf) + 4U, conf_mem[1]);
		setReg(get_frame_addr(adq_conf) + 8U, conf_mem[2]);
		setReg(get_frame_addr(adq_conf) + 12U, conf_mem[3]);

		if(imx296_setup(cam_conf) != 0)
		{
			print("[COPROC] Error configuring IMX296\n");
		}
		//vdma_run_channel(vdma_ch_cam);
		//while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1);
		non_valid_bytes = non_valid_rows * img_width;
		
	}
//
	// Reset pin configuration
//
	reset_pin_cfg.dev_base_addr = axi_gpio_base_addr;
	reset_pin_cfg.port = AXI_GPIO;
//
	// CONFIGURATION DMA 
	dma_ch_cfg.dev_base_addr = dma_conf_base_addr;
	dma_ch_cfg.direction = dma_rd;
	dma_ch_cfg.irqs = DMA_DMASR_IOC_IRQ;
	dma_ch_cfg.length = dma_conf_size;
	dma_ch_cfg.target_addr = get_frame_addr(copr_conf);
//
//
	// DATA DMA
		// MM2S DMA 
	dma_ch_data_rd.dev_base_addr = dma_data_base_addr;
	dma_ch_data_rd.direction = dma_rd;
	dma_ch_data_rd.irqs = 0U;
	dma_ch_data_rd.length = (uint32_t) img_width*img_height;
	dma_ch_data_rd.target_addr = get_frame_addr(copr_data_in);
//
		// S2MM DMA 
	dma_ch_data_wr.dev_base_addr = dma_data_base_addr;
	dma_ch_data_wr.direction = dma_wr;
	dma_ch_data_wr.irqs = 0U;
	dma_ch_data_wr.length = dma_data_s2mm_size;
	dma_ch_data_wr.target_addr = get_frame_addr(copr_data_out);
	
	dma_reset_core(dma_ch_cfg);
	dma_reset_core(dma_ch_data_rd);
//
	dma_config_channel(dma_ch_cfg);
	dma_config_channel(dma_ch_data_rd);
	dma_config_channel(dma_ch_data_wr);
	
	print("[COPROC] DMA Channels configured\n");
	if(camera){
		
		dma_run_channel(dma_ch_adq);
		dma_wait_idle(dma_ch_adq);

		for(int i = 0; i < 1; i++){
			vdma_run_channel(vdma_ch_cam);
			while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1){
			};
			
		}
		print("[COPROC] First frame obtained\n");
	}
//	
	reset_coproc();
	print("[COPROC] ORB Coprocessor initialized\n");
}

// Class destructor 
void ORB_coproc::shutdown() 
{
	if(camera)
	{
		gpio_set(mipi_a_pwup, LOW);
		gpio_close(mipi_a_pwup);

    	print("[COPROC] Camera switched off\n");
		camera = false;
	}
}

uint32_t ORB_coproc::version(){
	return get_version();
}
 
uint8_t ORB_coproc::config(float scale, uint8_t fast_threshold){
	uint32_t conf_mem[5]; 
	

	float inv_scale = 1.0 / scale;
	conf_mem[0] = img_width;
	conf_mem[1] = img_height;
	conf_mem[2] = (uint32_t)(scale * (1 << 14U));
	conf_mem[3] = (uint32_t)(inv_scale * (1 << 14U));
	conf_mem[4] = (uint32_t)(fast_threshold);

	setReg(get_frame_addr(copr_conf), conf_mem[0]);
	setReg(get_frame_addr(copr_conf) + 4U, conf_mem[1]);
	setReg(get_frame_addr(copr_conf) + 8U, conf_mem[2]);
	setReg(get_frame_addr(copr_conf) + 12U, conf_mem[3]);
	setReg(get_frame_addr(copr_conf) + 16U, conf_mem[4]);

	dma_run_channel(dma_ch_cfg);
	dma_wait_idle(dma_ch_cfg); // Active wait

	return 0;
}

uint32_t ORB_coproc::run(){

	uint32_t data_length;

	dma_run_channel(dma_ch_data_rd);
	dma_run_channel(dma_ch_data_wr);
	
	dma_wait_idle(dma_ch_data_rd);
	dma_wait_idle(dma_ch_data_wr);

	data_length = dma_get_length(dma_ch_data_wr);
	 	
	reset_coproc();

	return data_length;
}

void* ORB_coproc::get_results(uint8_t frame){

	void* data_out;
	
	data_out = get_frame_array((frame_type)(copr_data_out + frame));

	return data_out;
}

uint8_t ORB_coproc::update_frame(uint8_t frame){

	uint8_t ret;

	dma_ch_data_wr.target_addr = get_frame_addr((frame_type)(copr_data_out + frame));
	
	ret = dma_config_channel(dma_ch_data_wr);
	
	return ret;
}

int ORB_coproc::process_level(int level, float scale, int ThFAST)
{
	//std::unique_lock<std::mutex> lock(mtx);
	int n_data;

    update_frame(level);
    config(scale, ThFAST); 
    n_data = run();
        
	return n_data;
}

int ORB_coproc::process_level(int level, float scale, int iniThFAST, int minThFAST)
{
	//std::unique_lock<std::mutex> lock(mtx);
	int n_data;

    update_frame(level);
    config(scale, iniThFAST); 
    n_data = run();

    if(n_data == 0){
        update_frame(level);
        config(scale, minThFAST);
        n_data = run();
    }
        
	return n_data;
}

int ORB_coproc::process_level_dyn(int level, float scale, int iniThFAST, int minThFAST)
{
	//std::unique_lock<std::mutex> lock(mtx);
	int n_data;

	if(ORB_coproc::actu_matches < ORB_coproc::last_matches && ORB_coproc::fast_th > minThFAST)
	{
		--ORB_coproc::fast_th;
	}
	else if(ORB_coproc::actu_matches > ORB_coproc::last_matches && ORB_coproc::fast_th < iniThFAST)
	{
		//++ORB_coproc::fast_th;
		ORB_coproc::fast_th = iniThFAST;
	}

    update_frame(level);
    config(scale, ORB_coproc::fast_th); 
    n_data = run();

	return n_data;
}

int ORB_coproc::process_level_is_ini(int level, float scale, int iniThFAST, int minThFAST)
{
	//std::unique_lock<std::mutex> lock(mtx);
	int n_data;

    update_frame(level);
	if(is_ini)
	{
    	config(scale, iniThFAST); 
	}
	else
	{
		config(scale, minThFAST);
	}
    n_data = run();

	return n_data;
}

void ORB_coproc::set_is_ini(bool p_is_ini)
{
	is_ini = p_is_ini;
}

void ORB_coproc::update_matches(int matches)
{
	last_matches = actu_matches;
	actu_matches = matches;
}

uint32_t ORB_coproc::get_img_height(){
	return ORB_coproc::img_height;
}

uint32_t ORB_coproc::get_img_width(){
	return ORB_coproc::img_width;
}


void ORB_coproc::set_img_height(uint32_t img_height)
{
	ORB_coproc::img_height = img_height;
}
void ORB_coproc::set_img_width(uint32_t img_width)
{
	ORB_coproc::img_width = img_width;
}


uint8_t ORB_coproc::capture_frame(){
	//std::unique_lock<std::mutex> lock(mtx);
	if(camera)
	{
		dma_run_channel(dma_ch_adq);
		dma_wait_idle(dma_ch_adq);

		vdma_update_frame_addr(vdma_ch_cam, (uint32_t)(get_frame_addr(camera_frame) - non_valid_bytes));
		vdma_run_channel(vdma_ch_cam);
		while(vdma_get_irq(vdma_ch_cam, frmCntIrq) != 1)
		{
				usleep(2000);
		};	
	}
	else{
		return 1; // no camera available
	}

	return 0;
}

bool ORB_coproc::get_camera_status(){

	return camera;
}

bool ORB_coproc::is_initialized()
{
	return initialized;
}

void* ORB_coproc::get_camera_frame(){

	return get_frame_array(camera_frame);
}

void* ORB_coproc::get_coproc_in_frame(){

	return get_frame_array(copr_data_in);
}

void* ORB_coproc::get_results(){

	return get_frame_array(copr_data_out);
}

void ORB_coproc::set_exp_param(uint32_t shs){
	ORB_coproc::shs = shs;
	imx296_set_shs(shs);
}

void ORB_coproc::set_gain_param(uint16_t gain){
	ORB_coproc::gain = gain;
	imx296_set_gain(gain);
}


uint32_t ORB_coproc::get_exp_param()
{
	return ORB_coproc::shs;
}
uint32_t ORB_coproc::set_gain_param()
{
	return ORB_coproc::gain;
}

void ORB_coproc::initialize(uint32_t width, uint32_t height, uint32_t shs, uint16_t gain, bool camera, const std::string& dma_buff)
{
	ORB_coproc::img_width = width;
	ORB_coproc::img_height = height;
	ORB_coproc::shs = shs;
	ORB_coproc::gain = gain;
	ORB_coproc::camera = camera;
	ORB_coproc::initialized = true;
	//set_dma_buff_path(dma_buff.c_str());
}


ORB_coproc *ORB_coproc::get_instance()
{
	if(initialized)
	{
    	if(singleton==nullptr)
		{
    	    singleton = new ORB_coproc(ORB_coproc::img_width, ORB_coproc::img_height, ORB_coproc::shs, ORB_coproc::gain, ORB_coproc::camera);
    	}
	}
	else
	{
		printf("[COPROC] ERROR at get_instance - MISSING INITIALIZATION\n");
	}
    return singleton;
}


void setReg(uint32_t addr, uint32_t reg){

    mem_map mm;
	memmap_init(&mm, addr);

	memmap_write(mm, addr, reg);

	memmap_close(mm);

}

void reset_coproc(){
	axi_gpio_set_pin(reset_pin_cfg, 0U);
	usleep(500);
	axi_gpio_clear_pin(reset_pin_cfg, 0U);
}


void demosaic_config(uint32_t vid_width, uint32_t vid_height, uint8_t bayer_phase){
	XV_demosaic cfa;
    // DEMOSAIC CONFIGURATION
    XV_demosaic_Initialize(&cfa, XPAR_V_DEMOSAIC_0_DEVICE_ID);
	XV_demosaic_Set_HwReg_width(&cfa, vid_width);
	XV_demosaic_Set_HwReg_height(&cfa, vid_height);
	XV_demosaic_Set_HwReg_bayer_phase(&cfa, bayer_phase);
	XV_demosaic_EnableAutoRestart(&cfa);
	XV_demosaic_Start(&cfa);
}

void gamma_config(uint32_t vid_width, uint32_t vid_height, uint8_t data_width, float gamma_value){
	XV_gamma_lut gamma_inst;
	uint16_t* gamma_reg;
	gamma_reg = (uint16_t*)malloc((1<<data_width) * sizeof(uint16_t));
	int i;
    // GAMMA LUT CONFIGURATION
	//------------ Gamma calc
	for(i = 0; i<(1<<data_width); i++){
		gamma_reg[i] = (pow((i / (float)(1<<data_width)), (1/gamma_value)) * (float)(1<<data_width));
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

uint32_t get_frame_addr(frame_type n_frame){
 	return (uint32_t)u_dma_buf_get_physical_addr(frames_buffer, ((uint32_t)n_frame * (u_dma_buf_get_size(frames_buffer) / n_frames)));
}

void* get_frame_array(frame_type n_frame){
	
	void* virt_space;
	uint32_t img_height = ORB_coproc::get_img_height();
	uint32_t img_width = ORB_coproc::get_img_width();

	if(virtual_spaces[n_frame] == NULL){
		virt_space = u_dma_buf_get_virtual_space(frames_buffer, (uint32_t)((uint32_t)n_frame * (u_dma_buf_get_size(frames_buffer)  / n_frames)), img_width * img_height * 4U); // TO DO CHANGE bytes ppx
		virtual_spaces[n_frame] = virt_space;
	}
	else{
		virt_space = virtual_spaces[n_frame];
	}

	return virt_space;
}


uint32_t get_version(){
	uint32_t reg;

    mem_map mm;
	// memmap_init(&mm, version_reg_addr);

	// memmap_read(mm, version_reg_addr, &reg);

	// memmap_close(mm);

	return reg;
}

