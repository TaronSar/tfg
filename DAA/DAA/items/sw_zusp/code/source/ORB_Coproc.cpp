///    \file Lib_COPROC.cpp
///
///    \date 10 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    COPROC wrapper implementation.
///


#include <ORB_Coproc.h>


extern "C"
{
    extern Uint32 __frame_memory;       /// Pointer to beginning of frame section (linker)
    extern Uint32 _frame_memory_end;    /// Pointer to end of section
}


namespace Zusp
{    
    void* get_frame_addr(ORB_coproc::Frame_type n_frame);
    static Uint32 vdma_start = static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(ORB_coproc::none)));

    static Real adq_rescale_factor;
    static Uint32 non_valid_bytes;
    static ORB_coproc::ORB_coproc_sc source = ORB_coproc::image;

    /// Singleton initialization and virtual space definition
    ORB_coproc* ORB_coproc::singleton= NULL;
    static void* frame_spaces[coproc_frames];

    /// Total frame size
    static Uint32 frame_size = (_frame_memory_end - __frame_memory) / coproc_frames;
    

    ///  ***********************************************************************************

    ///	Writes a value 'register_value' in 'register_addr'
    void write_register(Uint32 register_addr,Uint32 register_value)
    {
        Hw_IO::hw_out32(register_addr, register_value);
    }


	/// \param	register_addr 	contains the register to be read from
	/// \return	The value read from the register.
	Uint32 read_register(Uint32 register_addr)
	{
		return Hw_IO::hw_in32(register_addr);
	}


    /// Get frame address
    void* get_frame_addr(ORB_coproc::Frame_type n_frame)
    {
        return frame_spaces[n_frame];
    }


    ///  ***********************************************************************************

    /// Constructor implementation
    ORB_coproc::ORB_coproc(ORB_coproc::ORB_coproc_sc img_source, Uint32 img_width, Uint32 img_height, Uint32 shs) :
        dma_ch_adq(DMA_adq_addr),
        vdma_ch_cam(VDMA_bd_addr, VDMA_write, VDMA_conf, &vdma_start, 1, img_width, (img_height + non_valid_rows)),
        dma_ch_cfg(DMA_conf_addr),
        dma_ch_data_rd(DMA_data_addr),
        reset_pin_cfg(AXI_GPIO_b_addr, 32, 32),
        dma_ch_data_wr(DMA_data_addr),
        i2c(I2C_master, static_cast<Uint32>(I2C0_baseaddr), I2C_mon_active, I2C_normal, I2C_transmit, I2C_100Khz),
        cam_conf(i2c, video_sc_width, video_sc_height, video_crop_top, video_crop_left, IMX296_b_phase, shs),
        gpio_COPROC(GPIO_bank3)
    {
        source = img_source;
        Uint8 cam_setup = 0;

        /// Frame spaces initialization
        for(Uint32 f_id = 0; f_id < coproc_frames; f_id++)
        {
            frame_spaces[f_id] = reinterpret_cast<void*>(__frame_memory + frame_size*f_id);
        }

        if(source == sc_camera)
        {
            Uint32 conf_mem[cam_id];

            gpio_COPROC.config_pin(MIPI_pwup,GPIO_output);
    //
            gpio_COPROC.set_val(MIPI_pwup,GPIO_low);
            Zusp::Sleep::sleep_us(wait_time_cam);
            gpio_COPROC.set_val(MIPI_pwup,GPIO_high);
            Zusp::Sleep::sleep_us(wait_time_cam);

            ///  V_PROC: 8-bit data width
            V_proc_SS VPSS_config(VPSS_base_addr,video_sc_width,video_sc_height,coproc_bit_wd);
            VPSS_config.setup();


            /// VDMA CONFIGURATION
            vdma_ch_cam.reset_channel();
            vdma_ch_cam.config_channel();
    //
            /// DEMOSAIC CONFIGURATION
            Demosaic cfa(Dem0_baseaddr);
            cfa.config(video_sc_width,video_sc_height,IMX296_b_phase);

            /// GAMMA LUT CONFIGURATION
            Gamma_LUT gamma_inst(GLUT0_A_b_addr);
            gamma_inst.config(video_sc_width,video_sc_height,color_depth,gamma_value);
    //
    
            adq_rescale_factor = (video_sc_width / (Real)img_width);

            Real inv_scale = 1.0 / adq_rescale_factor;
            conf_mem[coproc_cl] = video_sc_width;
            conf_mem[coproc_rw] = video_sc_height;
            conf_mem[coproc_sc] = static_cast<Uint32>(adq_rescale_factor * (1 << coproc_bit_dis));
            conf_mem[coproc_inv_sc] = static_cast<Uint32>(inv_scale * (1 << coproc_bit_dis));

            write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))), conf_mem[coproc_cl]);
            write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_wid_offs, conf_mem[coproc_rw]);
            write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_scl_offs, conf_mem[coproc_sc]);
            write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_inv_offs, conf_mem[coproc_inv_sc]);

            cam_setup = cam_conf.setup();
            if(cam_setup != 0)
            {
                ;   /// Handle error
            }
            else
            {
                img_cols = img_width;
                img_rows = img_height;
                non_valid_bytes = non_valid_rows * img_width;
            }
        }
        else
        {
            img_cols = img_width;
            img_rows = img_height;
        }
    
        
        /// Camera correctly configured
        if(cam_setup == 0)
        {
            
            if(source == sc_camera)
            {    
                vdma_ch_cam.run_channel();
                while(vdma_ch_cam.get_irq(VDMA_frm_cnt_irq) != 1)
                {
                    ;
                }
            }
        //	
            reset_coproc();
        }
    }


    ///  ***********************************************************************************

    // Class method to shutdown coproc 
    void ORB_coproc::shutdown() 
    {
        if(source == sc_camera)
        {
            /// Disable camera pin
            gpio_COPROC.set_val(MIPI_pwup, GPIO_low);
        }
    }

    
    ///  ***********************************************************************************

    Uint8 ORB_coproc::config(Real scale, Uint8 fast_threshold)
    {
        Uint32 conf_mem[coproc_conf]; 

        Real inv_scale = 1.0 / scale;
        conf_mem[coproc_cl] = img_cols;
        conf_mem[coproc_rw] = img_rows;
        conf_mem[coproc_sc] = static_cast<Uint32>(scale * (1 << coproc_bit_dis));
        conf_mem[coproc_inv_sc] = static_cast<Uint32>(inv_scale * (1 << coproc_bit_dis));
        conf_mem[cam_id] = static_cast<Uint32>(fast_threshold);

        write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))), conf_mem[coproc_cl]);
        write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_wid_offs, conf_mem[coproc_rw]);
        write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_scl_offs, conf_mem[coproc_sc]);
        write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_inv_offs, conf_mem[coproc_inv_sc]);
        write_register(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(copr_conf))) + coproc_cam_offs, conf_mem[cam_id]);

        dma_ch_cfg.read_channel->run_channel();
        dma_ch_cfg.read_channel->wait_idle();     /// Active wait

        return 0;
    }


    ///  ***********************************************************************************

    Uint32 ORB_coproc::run()
    {
        Uint32 data_length;

        dma_ch_data_rd.read_channel->run_channel();
        dma_ch_data_wr.write_channel->run_channel();
        
        dma_ch_data_rd.read_channel->wait_idle();
        dma_ch_data_wr.write_channel->wait_idle();

        data_length = dma_ch_data_wr.write_channel->get_length();
            
        reset_coproc();

        return data_length;
    }


    ///  ***********************************************************************************

    void* ORB_coproc::get_results(Uint8 frame)
    {
        void* data_out;
        
        data_out = get_frame_addr(static_cast<ORB_coproc::Frame_type>(copr_data_out + frame));

        return data_out;
    }


    ///  ***********************************************************************************

    Uint8 ORB_coproc::update_frame(Uint8 frame)
    {
        Uint8 ret;

        dma_ch_data_wr.write_channel->change_target(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(static_cast<ORB_coproc::Frame_type>(copr_data_out + frame)))));
        
        ret = dma_ch_data_wr.write_channel->config_channel();
        
        return ret;
    }


    ///  ***********************************************************************************

    int ORB_coproc::process_level(int level, Uint8 scale, int iniThFAST, int minThFAST)
    {
        int n_data;

        update_frame(level);
        config(scale, iniThFAST); 
        n_data = run();

        if(n_data == 0)
        {
            update_frame(level);
            config(scale, minThFAST);
            n_data = run();
        }
            
        return n_data;
    }


    ///  ***********************************************************************************

    Uint32 ORB_coproc::get_frame_rows()
    {
        return img_rows;
    }


    ///  ***********************************************************************************

    Uint32 ORB_coproc::get_frame_cols()
    {
        return img_cols;
    }


    ///  ***********************************************************************************

    Uint8 ORB_coproc::capture_frame()
    {
        Uint8 result = 0;

        if(source == sc_camera)
        {
            dma_ch_adq.read_channel->run_channel();
            dma_ch_adq.read_channel->wait_idle();

            vdma_ch_cam.update_frame_addr(static_cast<Uint32>(reinterpret_cast<uintptr_t>(get_frame_addr(f_camera))) - non_valid_bytes);
            vdma_ch_cam.run_channel();
            while(vdma_ch_cam.get_irq(VDMA_frm_cnt_irq) != 1)
            {
                ;
            }
        }
        else
        {
            result = 1;         /// no camera available
        }

        return result;
    }


    ///  ***********************************************************************************

    ORB_coproc::ORB_coproc_sc ORB_coproc::get_source()
    {
        return source;
    }


    ///  ***********************************************************************************

    void* ORB_coproc::get_camera_frame()
    {
        return get_frame_addr(f_camera);
    }


    ///  ***********************************************************************************

    void* ORB_coproc::get_coproc_in_frame()
    {
        return get_frame_addr(copr_data_in);
    }


    ///  ***********************************************************************************

    void* ORB_coproc::get_results()
    {
        return get_frame_addr(copr_data_out);
    }


    ///  ***********************************************************************************

    void ORB_coproc::set_exp_param(Uint32 shs)
    {
        cam_conf.set_shs(shs);
    }


    ///  ***********************************************************************************

    ORB_coproc *ORB_coproc::get_instance(ORB_coproc::ORB_coproc_sc source, Uint32 img_width, Uint32 img_height, Uint32 shs)
    {
        if(singleton==NULL)
        {
            singleton = new ORB_coproc(source,img_width,img_height,shs);
        }

        return singleton;
    }


    ///  ***********************************************************************************

    void ORB_coproc::reset_coproc()
    {
        reset_pin_cfg.set_pin(0U, GPIO_0);
        Zusp::Sleep::sleep_us(coproc_rst_t);
        reset_pin_cfg.clear_pin(0U, GPIO_0);
    }

}


