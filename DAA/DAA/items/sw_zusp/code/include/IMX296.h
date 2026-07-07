///    \file IMX296.h
///
///    \date 26 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    IMX296 class declaration.
///

#ifndef ZUSP_IMX296_H_
#define ZUSP_IMX296_H_

#include <Entypes.h>
#include <Parameters.h>
#include <I2C.h>


namespace Zusp
{
    class IMX296
    {
        public:
            IMX296(I2C& i2cport, Uint16 width, Uint16 height, Uint16 crop_top,
                    Uint16 crop_left, Uint16 bayer_phase, Uint32 shs);
            Uint8 setup();
            void set_shs(Uint32 shs);

        private:
            Uint16 imx_width;
            Uint16 imx_height;
            Uint16 imx_crop_top;
            Uint16 imx_crop_left;
            Uint16 imx_bayer_phase;
            Uint32 imx_shs;
            I2C port;
    };
}


#endif /// ZUSP_IMX296_H_