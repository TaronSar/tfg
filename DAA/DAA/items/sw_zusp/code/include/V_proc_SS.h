///    \file Printf.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Printf class implementation.
///


#ifndef ZUSP_V_PROC_SS_H_
#define ZUSP_V_PROC_SS_H_


#include <Parameters.h>
#include <Entypes.h>


namespace Zusp
{
    class V_proc_SS
    {
        public:
            V_proc_SS(  Uint32 addr, Uint32 proc_width,
                        Uint32 proc_height, Uint32 proc_data_width);
            Uint8 setup();
        
        private:
            Uint32 base_address;
            Uint32 width;
            Uint32 height;
            Uint32 data_width;
    };
}


#endif      /// ZUSP_V_PROC_SS_H_