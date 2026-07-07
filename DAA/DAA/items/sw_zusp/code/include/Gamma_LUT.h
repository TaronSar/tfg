///    \file Gamma_LUT.h
///
///    \date 2 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    Gamma_LUT class declaration.
///



#ifndef ZUSP_GAMMA_LUT_H_
#define ZUSP_GAMMA_LUT_H_


#include <Parameters.h>
#include <Entypes.h>
#include <Core_def.h>
#include <Hw_IO.h>
#include <stdlib.h>
#include <math.h>


/// ****************************************************************************************

/// CTRL
/// 0x0000 : Control signals
///          bit 0  - ap_start (Read/Write/COH)
///          bit 1  - ap_done (Read/COR)
///          bit 2  - ap_idle (Read)
///          bit 3  - ap_ready (Read)
///          bit 7  - auto_restart (Read/Write)
///          others - reserved
/// 0x0004 : Global Interrupt Enable Register
///          bit 0  - Global Interrupt Enable (Read/Write)
///          others - reserved
/// 0x0008 : IP Interrupt Enable Register (Read/Write)
///          bit 0  - Channel 0 (ap_done)
///          bit 1  - Channel 1 (ap_ready)
///          others - reserved
/// 0x000c : IP Interrupt Status Register (Read/TOW)
///          bit 0  - Channel 0 (ap_done)
///          bit 1  - Channel 1 (ap_ready)
///          others - reserved
/// 0x0010 : data signal of HwReg_width
///          bit 15~0 - HwReg_width[15:0] (Read/Write)
///          others   - reserved
/// 0x0014 : reserved
/// 0x0018 : data signal of HwReg_height
///          bit 15~0 - HwReg_height[15:0] (Read/Write)
///          others   - reserved
/// 0x001c : reserved
/// 0x0020 : data signal of HwReg_video_format
///          bit 15~0 - HwReg_video_format[15:0] (Read/Write)
///          others   - reserved
/// 0x0024 : reserved
/// 0x0800 ~
/// 0x0fff : Memory 'HwReg_gamma_lut_0' (1024 * 16b)
///          Word n : bit [15: 0] - HwReg_gamma_lut_0[2n]
///                   bit [31:16] - HwReg_gamma_lut_0[2n+1]
/// 0x1000 ~
/// 0x17ff : Memory 'HwReg_gamma_lut_1' (1024 * 16b)
///          Word n : bit [15: 0] - HwReg_gamma_lut_1[2n]
///                   bit [31:16] - HwReg_gamma_lut_1[2n+1]
/// 0x1800 ~
/// 0x1fff : Memory 'HwReg_gamma_lut_2' (1024 * 16b)
///          Word n : bit [15: 0] - HwReg_gamma_lut_2[2n]
///                   bit [31:16] - HwReg_gamma_lut_2[2n+1]
/// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)


/// ****************************************************************************************


namespace Zusp
{
    /// Class representation of Gamma LUT core
    class Gamma_LUT
    {
        public:
            Gamma_LUT(Uintptr base_addr);
            void config(Uint32 vid_width, Uint32 vid_height, Uint8 data_width, Real gamma_value);

        private:
            Uintptr base_address;       /// The base address of the core instance

            /// Private methods -----------------------------------------------------------

            void start();
            void en_auto_rst();

            void set_width(Uint32 data);
            void set_height(Uint32 data);
            void set_vid_format(Uint32 data);
            Uint32 get_GLUT0_B();
            Uint32 write_GLUT0_B(int offset, char* data, int length);
            Uint32 get_GLUT1_B();
            Uint32 write_GLUT1_B(int offset, char* data, int length);
            Uint32 get_GLUT2_B();
            Uint32 write_GLUT2_B(int offset, char* data, int length);
    };
}


#endif