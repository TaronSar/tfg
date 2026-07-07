///    \file Demosaic.h
///
///    \date 28 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    Demosaic class declaration.
///



#ifndef ZUSP_DEMOSAIC_H_
#define ZUSP_DEMOSAIC_H_


#include <Entypes.h>
#include <Parameters.h>
#include <Core_def.h>
#include <Hw_IO.h>


/// ****************************************************************************************

/// CTRL
/// 0x00 : Control signals
///        bit 0  - ap_start (Read/Write/COH)
///        bit 1  - ap_done (Read/COR)
///        bit 2  - ap_idle (Read)
///        bit 3  - ap_ready (Read)
///        bit 7  - auto_restart (Read/Write)
///        others - reserved
/// 0x04 : Global Interrupt Enable Register
///        bit 0  - Global Interrupt Enable (Read/Write)
///        others - reserved
/// 0x08 : IP Interrupt Enable Register (Read/Write)
///        bit 0  - Channel 0 (ap_done)
///        bit 1  - Channel 1 (ap_ready)
///        others - reserved
/// 0x0c : IP Interrupt Status Register (Read/TOW)
///        bit 0  - Channel 0 (ap_done)
///        bit 1  - Channel 1 (ap_ready)
///        others - reserved
/// 0x10 : Data signal of HwReg_width
///        bit 15~0 - HwReg_width[15:0] (Read/Write)
///        others   - reserved
/// 0x14 : reserved
/// 0x18 : Data signal of HwReg_height
///        bit 15~0 - HwReg_height[15:0] (Read/Write)
///        others   - reserved
/// 0x1c : reserved
/// 0x28 : Data signal of HwReg_bayer_phase
///        bit 15~0 - HwReg_bayer_phase[15:0] (Read/Write)
///        others   - reserved
/// 0x2c : reserved
/// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

/// ****************************************************************************************


namespace Zusp
{
    /// Class representation for the respective Demosaic core
    class Demosaic
    {
        public:
            Demosaic(Uint32 base_addr);
            void config(Uint32 vid_width, Uint32 vid_height, Uint8 bayer_phase);
        
        private:
            Uintptr base_address;       ///     Dem0_baseaddr

            /// Private methods ------------------------------------------------------

            void start();
            void en_auto_rst();

            void set_hw_width(Uint32 data);
            void set_hw_height(Uint32 data);
            void set_bayer_ph(Uint32 data);
    };

}

#endif      ///     ZUSP_DEMOSAIC_H_
