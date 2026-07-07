///    \file VDMA.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    VDMA class declaration.
///


#ifndef ZUSP_VDMA_H_
#define ZUSP_VDMA_H_


#include <Parameters.h>
#include <Entypes.h>


namespace Zusp
{
    /// VDMA direction 
    typedef enum
    {
        VDMA_write,     //  s2mm
        VDMA_read       //  mm2s
    } VDMA_direction;

    /// VDMA interrupt types
    typedef enum
    {
        VDMA_int_err = 4U,            //  s2mm
        VDMA_slv_err = 5U,
        VDMA_dec_err = 6U,
        VDMA_sof_early_err = 7U,
        VDMA_eol_early_err = 8U,
        VDMA_sof_late_err = 11U,
        VDMA_frm_cnt_irq = 12U,
        VDMA_dly_cnt_irq = 13U,
        VDMA_err_irq = 14U,
        VDMA_eol_late_err = 15U        //   mm2s
    } VDMA_irq;

    /// VDMA register types
    typedef enum
    {
        VDMA_cr, 
        VDMA_sr, 
        VDMA_str_addr,
        VDMA_h_size, 
        VDMA_v_size,
        VDMA_frm_dly_str    
    } VDMA_register;


    class VDMA
    {
        public:
            VDMA(Uint32 base_addr, VDMA_direction dir, Uint32 cr,
                 Uint32* start_addr, Uint32 n_frame, Uint32 size_h, Uint32 size_v);
            Uint8 reset_channel();
            Uint8 config_channel();
            Uint8 get_irq(VDMA_irq irq_id);
            Uint8 update_frame_addr(Uint32 frame_addr);
            Uint8 run_channel();

        private:
            Uint32 base_address;
            VDMA_direction direction;
            Uint32 cr_VDMA;
            Uint32 start_address[VDMA_frame_buff];
            Uint32 n_frame_buff;
            Uint32 h_size;
            Uint32 v_size;

            /// *****************************************************************************

            Uint32 get_reg_addr(VDMA_register reg);
            Uint8 set_start_addr(Uint32* start_addr, Uint8 n_str_addr);

    };
    
}


#endif      // ZUSP_VDMA_H_