///    \file Printf.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Printf class implementation.
///


#include <Printf.h>
#include <math.h>
#include <stdarg.h>


/// Initialize mutex variable
Zusp::Mutex_state Zusp::Printf::mutex_print = 0;
Zusp::UART uart_print(UART_0_baseaddr, 115200U);

namespace Zusp
{
    /// Add data to circular buffer
    /// \param[in]      byte        Byte character to be put in the circular buffer
    /// \param[in,out]  buffer      Buffer which changes in value for outbyte
    /// \param[in,out]  head        Circular buffer head changing value
    /// \param[in,out]  tail        Circular buffer tail changing value
    /// \param[in,out]  full        Indicator for buffer full
    ///
    /// \return     None
    static void put(Uint8 byte, 
                    Uint8* buffer, 
                    Uint32& head, 
                    Uint32& tail, 
                    bool& full)
    {
        /// \alg
        /// <ul>

        /// <li>    If the buffer is full
        if (full)
        {
            tail = (tail + 1) % circ_buf_len;
        }
        
        /// <li>    Change buffer related fields
        buffer[head] = byte;
        head = (head + 1) % circ_buf_len;
        full = (head == tail);
        /// </ul>
    }


    /// Verify if buffer is empty
    /// \param[in]  head    Head of circular buffer
    /// \param[in]  tail    Tail of circular buffer
    /// \param[in]  full    Buffer full flag
    ///
    /// \return
    ///         - TRUE:     Buffer is empty
    ///         - FALSE:    Buffer is not empty
    static bool buf_empty(Uint32 head, 
                          Uint32 tail, 
                          bool full)
    {

        /// \alg
        /// <ul>

        /// <li>    Return buffer is empty condition
        return (!full && (head == tail));
        /// </ul>
    }


    /// Get data from circular buffer
    /// \param[in]  buffer      Buffer from which data is collected
    /// \param[in]  head        Head of circular buffer
    /// \param[in]  tail        Tail of circular buffer
    /// \param[in]  full        Indicator that buffer is full
    ///
    /// \return
    ///         - 0:        Buffer is empty
    ///         - byte:     Buffer is not empty (a byte is returned)
    static Uint8 get(Uint8* buffer, 
                     Uint32& head, 
                     Uint32& tail, 
                     bool& full)
    {
        /// \alg
        /// <ul>
        
        /// <li>    Check if the buffer is not empty
        if (!buf_empty(head, tail, full))
        {
            /// <li>    Return corresponding byte in tail of buffer
            Uint8 byte = buffer[tail];
            full = false;
            tail = (tail + 1) % circ_buf_len;
            return byte;
        }

        /// <li>    If it is empty, return 0
        return 0;
        /// </ul>
    }


    /// Output byte through UART driver instance (UART0)
    /// \param[in]  data        Byte to be printed
    ///
    /// \return     None
    void out_byte(Uint8 data)
    {
        /// \alg
        /// <ul>
        static Uint8 circular_buffer[circ_buf_len];
        static Uint32 head = 0;
        static Uint32 tail = 0;
        static bool full = false;

        /// <li>    Handle special character bel_char
        if (data == '\a')
        {
            put(bel_char, circular_buffer, head, tail, full);
        }
        /// <li>    Handle special character bs_char
        else if (data == '\b')
        {
            put(bs_char, circular_buffer, head, tail, full);
        }
        /// <li>    Handle special character r_char
        else if (data == '\r')
        {
            put(r_char, circular_buffer, head, tail, full);
        }
        /// <li>    Handle special character nl_char
        else if (data == '\n')
        {
            put(r_char, circular_buffer, head, tail, full);
            put(nl_char, circular_buffer, head, tail, full);
        }
        /// <li>    Rest of characters to be printed
        else
        {
            put(data, circular_buffer, head, tail, full);
        }

        /// <li>    Send data to UART when necessary
        while (!buf_empty(head, tail, full))
        {
            Uint8 byteToSend = get(circular_buffer, head, tail, full);

            /// <li>    Send byte through UART
            uart_print.send_byte(byteToSend);
        }
        /// </ul>
    }


    /// Adds padding characters if certain conditions are met
    /// \param[in]  l_flag      Flag to indicate padding should be applied
    ///                         or not (non-zero for apply)
    /// \param[in]  params      List of parameters for padding
    ///
    /// \return     None
    void padding(const int32 l_flag, const Printf::Params* params)
    {
        /// \alg
        /// <ul>
        int32 i;

        /// <li>    Check if padding should be applied and the current length
        ///         is less than the desired width
        if ((params->do_padding != 0) && (l_flag != 0) && (params->len < params->width))
        {
            /// <li>    Output padding characters
            i = (params->len);
            for (; i < (params->width); i++)
            {
                out_byte(params->pad_character);
            }
        }
        /// </ul>
    }


    /// Print string chain through UART driver
    /// \param[in]  local_pt    Pointer to string chain
    /// \param[in]  params      Parameters for printing
    ///
    /// \return     None
    void outs(const char_ptr local_pt, Printf::Params* params)
    {
        /// \alg
        /// <ul>
        char_ptr local_ptr;
        local_ptr = local_pt;

        /// <li>    Pad on left if needed
        if (local_ptr != NULL)
        {
            /// <li>    Get length of string
            int32 len = 0;
            while (local_ptr[len] != '\0')
            {
                len++;
            }
            params->len = len;

            /// <li>    Manage padding
            padding(!(params->left_flag), params);

            /// <li>    Move string to the buffer
            while (((*local_ptr) != (char)0) && ((params->precision) != 0))
            {
                (params->precision)--;
                out_byte(*local_ptr);
                local_ptr += 1;
            }
        }

        /// <li>    Manage padding
        padding(params->left_flag, params);
        /// </ul>
    }

    
    /// Printing of 64-bit number
    /// \param[in]  n           Number to print
    /// \param[in]  base        Base of printing
    /// \param[in]  params      Parameters used for print
    ///
    /// \return     None
    void outnum_32(const int32 n, 
                   const int32 base, 
                   Printf::Params* params)
    {
        /// \alg
        /// <ul>
        int32 negative;
        int32 i;
        char out_buf[mid_size_buf];
        const char digits[] = "0123456789ABCDEF";
        Uint32 num;

        /// <li>    Fill buffer with 0s (beginning)
        for (i = 0; i < mid_size_buf; i++)
        {
            out_buf[i] = '0';
        }

        /// <li>    Check if number is negative
        if ((params->unsigned_flag == 0) && (base == base_10) && (n < 0))
        {
            negative = 1;
            num = (-(n));
        }
        else 
        {
            num = n;
            negative = 0;
        }

        /// <li>    Build number
        i = 0;
        /// <li>    If the number is null
        if (num == 0)
        {
            out_buf[i] = '0';
            i++;
        }
        else
        {
            /// <li>    Build number (backwards) in out_buf
            while (num > 0)
            {
                out_buf[i] = digits[(num % (Uint32)base)];
                i++;
                num /= base;
            }
        }

        /// <li>    If negative flag is set
        if (negative != 0)
        {
            out_buf[i] = '-';
            i++;
        }

        out_buf[i] = '\0';
        i--;

        /// <li>    Get buffer length
        int32 len = 0;
        while (out_buf[len] != '\0')
        {
            len++;
        }
        params->len = len;

        /// <li>    Manage padding
        padding(!(params->left_flag), params);

        /// <li>    Move the converted number to the buffer and
        ///         add in the padding where needed.
        while (&out_buf[i] >= out_buf)
        {
            out_byte(out_buf[i]);
            i--;
        }

        /// <li>    Manage padding
        padding(params->left_flag, params);
        /// </ul>
    }


    /// Printing of 64-bit number
    /// \param[in]  n           Number to print
    /// \param[in]  base        Base of printing
    /// \param[in]  params      Parameters used for print
    ///
    /// \return     None
    void outnum_64(const int64 n, 
                   const int32 base, 
                   Printf::Params* params)
    {
        /// \alg
        /// <ul>
        int32 negative;
        int32 i;
        char out_buf[max_size_buf];
        const char digits[] = "0123456789ABCDEF";
        Uint64 num;

        /// <li>    Fill buffer with 0s (beginning)
        for (i = 0; i < max_size_buf; i++)
        {
            out_buf[i] = '0';
        }

        /// <li>    Check if number is negative
        if ((params->unsigned_flag == 0) && (base == base_10) && (n < 0))
        {
            negative = 1;
            num = (-(n));
        }
        else
        {
            num = (n);
            negative = 0;
        }

        /// <li>    Build number in buffer
        i = 0;
        /// <li>    If number is 0
        if (num == 0)
        {
            out_buf[i] = '0';
            i++;
        }
        else
        {
            /// <li>    Build number (backwards) in out_buf
            while (num > 0)
            {
                out_buf[i] = digits[(num % (Uint32)base)];
                i++;
                num /= base;
            }
        }

        /// <li>    Negative flag
        if (negative != 0)
        {
            out_buf[i] = '-';
            i++;
        }

        out_buf[i] = '\0';
        i--;

        /// <li>    Get buffer length
        int32 len = 0;
        while (out_buf[len] != '\0')
        {
            len++;
        }
        params->len = len;

        /// <li>    Move the converted number to the buffer and
        ///         add in the padding where needed.
        padding(!(params->left_flag), params);
        while (&out_buf[i] >= out_buf)
        {
            out_byte(out_buf[i]);
            i--;
        }

        /// <li>    Manage padding
        padding(params->left_flag, params);
        /// </ul>
    }


    /// Implementation of strcpy (Standard C++)
    /// \param[in,out]  dest    Destination of copy
    /// \param[in]      src     Source of copying process
    ///
    /// \return     Chain copied
    char_ptr p_strcpy(char_ptr dest, const char_ptr src)
    {
        /// \alg
        /// <ul>
        char_ptr original_dest = dest;
        char_ptr src_dest = src;

        /// <li>    While not in the end of chain,
        ///         copy values to destination
        while (*src_dest != '\0')
        {
            *dest = *src_dest;
            dest++;
            src_dest++;
        }
        *dest = '\0';

        return original_dest;
        /// </ul>
    }


    /// Implementation of tolower (Standard C++)
    /// \param[in]  ch      Character to convert to lower case
    ///
    /// \return     Character in lower case
    Uint8 p_tolower(Uint8 ch)
    {
        /// \alg
        /// <ul>

        /// <li>    Convert character to lower case
        if (ch >= 'A' && ch <= 'Z')
        {
            return ch + mid_size_buf;
        }

        return ch;
        /// </ul>
    }


    /// Convert integer value to string
    /// \param[in]  value   Number to convert to string
    ///
    /// \return     None
    void int_to_string(int value, 
                       char* buf, 
                       int base)
    {
        /// \alg
        /// <ul>
        char temp[32];
        int i = 0, j;

        /// <li>    Handle the special case for 0
        if (value == 0)
        {
            buf[i++] = '0';
        }

        else
        {
            /// <li>    Handle negative values
            if (value < 0 && base == base_10)
            {
                buf[i++] = '-';
                value = -value;
            }

            /// <li>    Convert the integer part to a string
            while (value > 0)
            {
                int digit = value % base;
                temp[i++] = (digit < base_10) ? (digit + '0') : (digit - base_10 + 'a');
                value /= base;
            }

            /// <li>    Reverse the string
            for (j = 0; j < i; j++)
            {
                buf[j] = temp[i - j - 1];
            }
        }
        buf[i] = '\0';
        /// </ul>
    }


    /// Get number from string
    /// \param[in]  line_ptr    Pointer for string number
    ///
    /// \return     Number (32-bit integer)
    int32 get_num(char_ptr& line_ptr)
    {
        /// \alg
        /// <ul>
        int32 n = 0;

        /// <li>    Get number in base 10 (decimal)
        while (*line_ptr >= '0' && *line_ptr <= '9')
        {
            n = ((n * base_10) + (*line_ptr - '0'));
            line_ptr++;
        }

        return n;
        /// </ul>
    }


    /// Convert float number to string chain
    /// \param[in]  value       Float number to convert to string
    /// \param[in]  buffer      
    void float_to_string(Real64 value, 
                         char* buffer, 
                         int precision)
    {
        /// \alg
        /// <ul>
        int integer_part = (int)value;
        Real64 fractional_part = value - integer_part;
        int i = 0;

        /// <li>    Convert integer part of float to string
        int_to_string(integer_part, buffer, base_10);

        /// <li>    Get buffer length
        Uint64 len = 0;
        while (buffer[len] != '\0')
        {
            len++;
        }
        i += len;

        if (precision > 0)
        {
            buffer[i++] = '.';

            /// <li>    Iterate over the number of decimal places
            for (int j = 0; j < precision; j++)
            {
                fractional_part *= base_10;
                int digit = (int)fractional_part;
                buffer[i++] = '0' + digit;
                fractional_part -= digit;
            }

            /// <li>    Now handle rounding
            fractional_part *= base_10;
            int next_digit = (int)fractional_part;

            /// <li>    Round if next digit is >= 5
            if (next_digit >= 5)
            {
                /// <li>    Go back to the last digit we wrote
                i--;

                /// <li>    Handle carry-over
                while (i >= 0 && buffer[i] == '9')
                {
                    buffer[i] = '0';
                    i--;
                }
                if (i >= 0 && buffer[i] != '.')
                {
                    buffer[i]++;
                }
                /// <li>    Special case when integer part also needs to be rounded
                else if (i < 0)
                {
                    /// <li>    Add '1' at the start of the buffer
                    buffer[i + 1] = '1';
                }
            }

            buffer[i + 1] = '\0';
        }
        else
        {
            buffer[i] = '\0';
        }
        /// </ul>
    }


    /// Count number of decimal digits (float/double data)
    /// \param[in]  value   Float value for decimal counting
    ///
    /// \return     None
    Uint16 count_decimal(Real64 value)
    {
        /// \alg
        /// <ul>
        Uint16 count = 0;

        /// <li>    There can't be three or more 9s or 0s contiguous for
        ///         printing due to technical limitations for the Ultrascale+,
        ///         else the algorithm will return in an error.
        Real precision = 0.001;
        Real min_precision = 0.00001;
        Real64 fractional_part = value - (int)value;

        /// <li>    Count amount of decimal values
        while ((((1.0 - fractional_part) > precision) && 
                (fractional_part > precision) && 
                (count < base_10)) ||
                (fractional_part < min_precision))
        {
            fractional_part *= base_10;
            fractional_part -= (int)fractional_part;
            count++;
        }

        return count;
        /// </ul>
    }


    /// Outbyte of float data
    /// \param[in]  f           Float number
    /// \param[in]  params      Set of parameters used for
    ///                         float printing
    /// \return     None
    void out_float(Real f, Printf::Params* params)
    {
        /// \alg
        /// <ul>
        char outbuf[64];

        /// <li>    Obtain quantity of float decimals
        int32 decimals = (int32)count_decimal(f);

        /// <li>    If number has less decimals than precision asked
        if (decimals < params->precision)
        {
            float_to_string((Real64)f, outbuf, decimals);
        }
        /// <li>    If not, print number with user precision asked
        else
        {
            float_to_string((Real64)f, outbuf, params->precision);
        }

        /// <li>    Obtain buffer length
        Uint64 len = 0;
        while (outbuf[len] != '\0')
        {
            len++;
        }
        params->len = len;

        /// <li>    Manage padding
        padding(!(params->left_flag), params);

        /// <li>    Print buffer
        for (Uint32 j = 0; j < params->len; j++)
        {
            out_byte(outbuf[j]);
        }

        /// <li>    Manage padding
        padding(params->left_flag, params);
    }


    /// Printf main function
    /// \param[in]  string_ptr      Pointer to string to be
    ///                             printed through UART device 
    /// \return     None
    void Printf::printf(const char* string_ptr, ...)
    {
        /// \alg
        /// <ul>
        va_list argp;

        /// <li>    Mutex locking for core isolation
        Zusp::Mutex::lock(&mutex_print);

        /// <li>    Get arguments and print string
        va_start(argp, string_ptr);
        vprintf(string_ptr, argp);
        va_end(argp);

        /// <li>    Mutex free
        Zusp::Mutex::unlock(&mutex_print);
        /// </ul>
    }


    /// Manage string print through UART driver
    /// \param[in]  string_ptr      Pointer to string chain
    /// \param[in]  argp            Arguments list
    ///
    /// \return     None
    void Printf::vprintf(const char* string_ptr, va_list argp)
    {
        /// \alg
        /// <ul>
        int32 check;
        Params par;

        char* ctrl = (char*)string_ptr;

        /// <li>    Print chain until its end
        while (*ctrl != '\0')
        {
            /// <li>    If the character doesn't mean a
            ///         parameter printing
            if (*ctrl != '%')
            {
                out_byte(*ctrl);
                ctrl++;
            }

            else
            {
                check = 0;
                par.dt_flag = 0;
                par.lg_flag = 0;
                par.unsigned_flag = 0;
                par.left_flag = 0;
                par.do_padding = 0;
                par.pad_character = ' ';

                /// <li>    Default precision (very large)
                par.precision = 32767;

                /// <li>    Default width
                par.width = 0;
                par.len = 0;

                ctrl++;

                while (*ctrl != '\0')
                {
                    /// <li>    Convert character to lower value
                    char ch = (Uint8)*ctrl;
                    ch = p_tolower(ch);

                    /// <li>    If the character is a number
                    if (ch >= (Uint8)('0') && ch <= (Uint8)('9'))
                    {
                        /// <li>    Get precision if dot flag is set
                        if (par.dt_flag != 0)
                        {
                            par.precision = get_num(ctrl);
                            par.dt_flag = 0;
                        }
                        
                        else
                        {
                            /// <li>    Manage padding
                            if (ch == (Uint8)'0')
                            {
                                par.pad_character = '0';
                            }
                            if (ctrl != NULL)
                            {
                                par.width = get_num(ctrl);
                            }
                            par.do_padding = 1;
                        }

                        if (ctrl != NULL)
                        {
                            ctrl -= 1;
                        }
                    }
                    /// <li>    Left flag configuration
                    else if (ch == (Uint8)'-')
                    {
                        par.left_flag = 1;
                    }
                    /// <li>    Long flag set
                    else if (ch == 'l')
                    {
                        par.lg_flag = 1;
                    }
                    /// <li>    Pointer/direction flag set
                    else if (ch == 'x' || ch == 'X')
                    {
                        /// <li>    Print number set as argument in hex base
                        outnum_64((Uint64)va_arg(argp, void*), 16, &par);
                        check = 1;
                    }
                    /// <li>    Integer flag
                    else if (ch == 'i' || ch == 'd' || ch == 'u')
                    {
                        /// <li>    Unsigned flag set
                        if (ch == 'u')
                        {
                            par.unsigned_flag = 1;
                        }
                        /// <li>    If the integer is long, print with outnum_64
                        if (par.lg_flag)
                        {
                            outnum_64((int64)va_arg(argp, int64), min_number, &par);
                        }

                        else
                        {
                            outnum_32(va_arg(argp, int32), min_number, &par);
                        }
                        check = 1;
                    }
                    /// <li>    Float printing argument
                    else if (ch == 'f')
                    {
                        out_float((float)va_arg(argp, Real64), &par);
                        check = 1;
                    }
                    /// <li>    String printing argument
                    else if (ch == 's')
                    {
                        outs(va_arg(argp, char*), &par);
                        check = 1;
                    }
                    /// <li>    Character printing argument
                    else if (ch == 'c')
                    {
                        out_byte((char)va_arg(argp, int32));
                        check = 1;
                    }
                    /// <li>    Dot flag set
                    else if (ch == (Uint8)'.')
                    {
                        par.dt_flag = 1;
                    }
                    /// <li>    Print the characters '%' and
                    ///         'ch' character in other case
                    else
                    {
                        out_byte('%');
                        out_byte(ch);
                        check = 1;
                    }

                    if (check)
                    {
                        /// <li>    Get out of inner loop
                        ///         if command successful
                        break;
                    }

                    ctrl++;
                }

                ctrl++;
            }
        }
        /// </ul>
    }
}