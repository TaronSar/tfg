///    \file Exception.h
///
///    \date 29 ago. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Exception definitions.
///

#ifndef ZUSP_EXCEPTION_H_
#define ZUSP_EXCEPTION_H_

#include <Parameters.h>

namespace Zusp{
    namespace Exception{

        /// Exception handler typedef
        typedef void (*Exc_handler)(void* data);

        /// Exception struct
        typedef struct 
        {
                Exc_handler handler; /// Handler of exception
                void* data;          /// Data of exception
        }
        Vec_table_entry;
    };
}


#endif // ZUSP_EXCEPTION_H_