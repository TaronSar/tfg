///    \file Lib_COPROC.h
///
///    \date 2 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    COPROC wrapper declaration.
///


#ifndef ZUSP_LIB_COPROC_H_
#define ZUSP_LIB_COPROC_H_


#include <Entypes.h>
#include <Parameters.h>
#include <Hw_IO.h>
#include <Demosaic.h>
#include <Gamma_LUT.h>
#include <GPIO.h>
#include <AXI_GPIO.h>
#include <IMX296.h>
#include <DMA.h>
#include <VDMA.h>
#include <V_proc_SS.h>
#include <Printf.h>
#include <Sleep.h>



namespace Zusp
{

    /// \brief ORB coprocessors class.
    class ORB_coproc
    {
        public:
            /// Frame type definition (COPROC use)
            typedef enum
            {
                none = 0,
                f_camera = 1,
                copr_conf = 2,
                copr_data_in = 4,
                adq_conf = 5,
                copr_data_out = 6
            } Frame_type;


            /// Data source
            typedef enum
            {
                sc_camera = 0,
                image = 1,
                video = 2
            } ORB_coproc_sc;

            /// Singletons should not be cloneable.
            ORB_coproc(ORB_coproc &other) = delete;

            /// Singletons should not be assignable.
            void operator=(const ORB_coproc &) = delete;
            
            /// This is the static method that controls the access to the singleton
            /// instance. On the first run, it creates a singleton object and places it
            /// into the static field. On subsequent runs, it returns the client existing
            /// object stored in the static field. 
            static ORB_coproc* get_instance(ORB_coproc_sc source, Uint32 img_width, Uint32 img_height, Uint32 shs);
            
            /// \brief Configuration of coprocessors.
            Uint8 config(Real scale, Uint8 fast_threshold);
            int process_level(int level, Uint8 scale, int iniThFAST, int minThFAST);

            /// \brief Execute coprocessors.
            Uint32 run();
            void* get_results(Uint8 frame);
            Uint8 update_frame(Uint8 frame);

            void shutdown();

            void* get_camera_frame();
            void* get_coproc_in_frame();
            void* get_results();

            ORB_coproc_sc get_source();

            Uint8 capture_frame();

            Uint32 get_frame_rows();
            Uint32 get_frame_cols();
            void set_exp_param(Uint32 shs);
            void reset_coproc();

        protected:
            /// \brief ORB_coproc class constructor, set the picture to be copied to the pysical memory.
            /// \param config structure with coprocessors configuration.
            /// \param img_width image width.
            /// \param img_height image height.
            ORB_coproc(ORB_coproc_sc source, Uint32 img_width, Uint32 img_height, Uint32 shs);

        private:
            static ORB_coproc* singleton;

            DMA dma_ch_adq;
            VDMA vdma_ch_cam;
            AXI_GPIO reset_pin_cfg;
            DMA dma_ch_cfg;
            DMA dma_ch_data_rd;
            DMA dma_ch_data_wr;
            I2C i2c;
            IMX296 cam_conf;
            Uint32 img_rows;
            Uint32 img_cols;
            GPIO gpio_COPROC;
    };
}


#endif      /// ZUSP_LIB_COPROC_H_