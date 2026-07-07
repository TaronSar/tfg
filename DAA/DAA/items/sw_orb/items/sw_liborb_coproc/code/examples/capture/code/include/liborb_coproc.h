

extern "C"{
	#include <stdlib.h>
	#include <fcntl.h>
	#include <stdio.h>
	#include <math.h>
	#include <time.h>
	#include <unistd.h>
	#include <unistd.h>
}

#include <vector>
#include <stdint.h>


typedef enum {
    CAMERA = 0,
    IMAGE = 1,
    VIDEO = 2
} ORB_coproc_source;


typedef enum {
    RAW8 = 0,
    RAW10 = 1
} ORB_coproc_image_format;


/**
 * @brief ORB coprocessors class.
 *
 */
class ORB_coproc
{
		const uint32_t bytes_per_pixel			= 1U;	

		const uint32_t video_crop_left			= 0U; 
		const uint32_t video_crop_top			= 0U;

		const uint32_t powup_waiting_time_camera = 500000U; //us
	private:
		const uint32_t bits_color_depth			= 8U;

		const float gamma_value					= 1.2;

		const uint32_t u_dma_buf_size 			= 64U * 1024U * 1024U;
		const uint32_t u_dma_buf_id 			= 0U;

		const uint32_t axi_gpio_base_addr 		= 0xB0060000U;
		const uint32_t v_proc_ss_base_addr 		= 0xB0000000U;
		const uint32_t pix_pack_base_addr 		= 0xB0010000U;

		const uint32_t reserved_mem_area_addr 	= 0x60000000U;
		const uint32_t frame_mem_area_size 		= 0x200000U;

		const uint32_t vdma_data_base_addr 		= 0xB0030000U;

		const uint32_t dma_conf_base_addr 		= 0xA0000000U;
		const uint32_t dma_data_base_addr 		= 0xA0010000U;

		const uint32_t dma_conf_size 		    = 0x20U;
		const uint32_t dma_data_s2mm_size	    = 0x01000000U;

		const uint32_t non_valid_rows			= 0U; //-> valid for 640x480; 16U -> valid for 1280x960
	
	protected:
    /**
     * @brief ORB_coproc class constructor, set the picture to be copied to the pysical memory.
     * @param config structure with coprocessors configuration.
     * @param img_width image width.
     * @param img_height image height.
     */
    ORB_coproc(ORB_coproc_source source, uint32_t img_width, uint32_t img_height, uint32_t shs);

	static ORB_coproc* singleton;

	public:


    	/**
    	 * Singletons should not be cloneable.
    	 */
    	ORB_coproc(ORB_coproc &other) = delete;
    	/**
    	 * Singletons should not be assignable.
    	 */
    	void operator=(const ORB_coproc &) = delete;
		

    	/**
    	 * This is the static method that controls the access to the singleton
    	 * instance. On the first run, it creates a singleton object and places it
    	 * into the static field. On subsequent runs, it returns the client existing
    	 * object stored in the static field. 
    	 */


    	static ORB_coproc *get_instance(ORB_coproc_source source, uint32_t img_width, uint32_t img_height, uint32_t shs);
    	/**
    	 * @brief Configuration of coprocessors.
    	 */
		uint8_t config(float scale, uint8_t fast_threshold);

    	/**
    	 * @brief Execute coprocessors.
    	 */
		uint32_t run();
		void* get_results(uint8_t frame);
		uint8_t update_frame(uint8_t frame);

		void shutdown();

		void* get_camera_frame();
		void* get_coproc_in_frame();

		void* get_results();

		ORB_coproc_source get_source();

		uint8_t capture_frame();

		uint32_t get_frame_rows();
		uint32_t get_frame_cols();
};


