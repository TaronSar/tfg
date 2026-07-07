///    \file Pixel_Pack.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Pixel_Pack class declaration.
///


#ifndef ZUSP_PIXEL_PACK_H_
#define ZUSP_PIXEL_PACK_H_


#include <Parameters.h>
#include <Entypes.h>


namespace Zusp
{
    /// Pixel_pack mode set
    typedef enum
    {
        mode_v24,
        mode_v32,
        mode_v8,
        mode_v16,
        mode_v16C
    } Pixel_pack_mode;


    class Pixel_pack
    {
        public:
            Pixel_pack(Uint32 addr, Pixel_pack_mode pixel_mode);
            Uint8 setup();

        private:
            Uint32 base_address;
            Pixel_pack_mode mode;
    };

}


#endif // ZUSP_PIXEL_PACK_H_