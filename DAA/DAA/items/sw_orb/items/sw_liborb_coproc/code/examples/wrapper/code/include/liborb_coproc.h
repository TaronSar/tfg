

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


    	static ORB_coproc *get_instance();
    	/**
    	 * @brief Configuration of coprocessors.
    	 */
		uint8_t config(float scale, uint8_t fast_threshold);
		int process_level(int level, float scale, int iniThFAST, int minThFAST);
		int process_level(int level, float scale, int ThFAST);
		int process_level_dyn(int level, float scale, int iniThFAST, int minThFAST);
		int process_level_is_ini(int level, float scale, int iniThFAST, int minThFAST);
		static void update_matches(int matches);
		static void set_is_ini(bool p_is_ini);
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

		bool get_camera_status();

		uint8_t capture_frame();

		static uint32_t get_img_height();
		static uint32_t get_img_width();
		static uint32_t get_exp_param();
		static uint32_t set_gain_param();
		static void set_img_height(uint32_t img_height);
		static void set_img_width(uint32_t img_width);
		static void set_exp_param(uint32_t shs);
		static void set_gain_param(uint16_t gain);
		
		static void initialize(uint32_t width, uint32_t height, uint32_t shs, uint16_t gain, bool camera);


	protected:
    	/**
    	 * @brief ORB_coproc class constructor, set the picture to be copied to the pysical memory.
    	 * @param config structure with coprocessors configuration.
    	 * @param img_width image width.
    	 * @param img_height image height.
    	 */
    	ORB_coproc(uint32_t img_width, uint32_t img_height, uint32_t shs, uint16_t gain, bool camera_enable);

		static ORB_coproc* singleton;
		static int fast_th;
		static int last_matches;
		static int actu_matches;
		static bool is_ini;
		static uint32_t img_height;
		static uint32_t img_width;
		static uint32_t shs;
		static uint16_t gain;
		static bool camera;
		static bool initialized;

	private:

    	std::mutex mtx;
};


