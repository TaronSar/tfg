///    \file Printf.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Printf class declaration.
///


#ifndef ZUSP_PRINTF_H_
#define ZUSP_PRINTF_H_

#include <UART.h>
#include <Mutex_spinlock.h>
#include <stdarg.h>

namespace Zusp 
{

    typedef char* char_ptr;

    class Printf
    {
    public:
        ///  Parameters for vprintf use (precision, length, padding, ...)
        struct Params
        {
            int32 len;              /// length 
            int32 width;            /// width of number 
            int32 precision;        /// precision for float/double number
            int32 do_padding;       /// do padding 
            int32 left_flag;        /// left flag 
            int32 unsigned_flag;    /// unsigned flag 
            int32 lg_flag;
            int32 dt_flag;
            char pad_character;     /// pad character 
        };

        ///****************************************************************************/
        /// \param string_ptr pointer to string for printing
        /// 
        /// \return void data
        /// 
        static void printf( const char* string_ptr, ...);

    private:
        ///  Mutex instance for unique core prints
        static Mutex_state mutex_print;

        ///*****************************************************************************/
        /// \param argp   indicates the possible parameters to be printed in the string,
        ///               by adding the "%" option.
        ///
        static void vprintf(const char* string_ptr, va_list argp);
    };
}

#endif