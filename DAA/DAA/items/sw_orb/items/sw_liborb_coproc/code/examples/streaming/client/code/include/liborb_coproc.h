

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


/**
 * @brief ORB coprocessors class.
 *
 */
class ORB_coproc
{
	
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
		int process_level(int level, uint8_t scale, int iniThFAST, int minThFAST);
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




	protected:
    	/**
    	 * @brief ORB_coproc class constructor, set the picture to be copied to the pysical memory.
    	 * @param config structure with coprocessors configuration.
    	 * @param img_width image width.
    	 * @param img_height image height.
    	 */
    	ORB_coproc(ORB_coproc_source source, uint32_t img_width, uint32_t img_height, uint32_t shs);

		static ORB_coproc* singleton;
};


