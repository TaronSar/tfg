///    \file UART.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    UART class declaration.
///

#ifndef ZUSP_UART_H_
#define ZUSP_UART_H_

#include <Parameters.h>

namespace Zusp
{
    /// UART id set for two UARTs used
    enum UART_id
    {
        UART_0,
        UART_1
    };

    class UART
    {
    public:
        /// UART constructor
        /// \param[in]  bd_rate     Baud rate used for UART initialization
        /// \param[in]  base_addr   Base address for UART instance
        ///
        /// \return     Zusp::UART instance
        UART(const Uint32 base_addr, const Uint32 bd_rate);

        /// Data bit sending following standard Xillinx protocol.
        /// Zynq UltraScale+ TRM -- UG1085 (v2.4) -- page 609
        /// \param[in]  data    Data byte to be sent
        ///
        /// \return     None
        void send_byte(const Uint8 data);

        /// Wait for transmission to complete
        ///
        /// \return     None
        void wait_transmit_done();

        /// Method to check if the UART device is initialized
        ///
        /// \return is_ready variable
        ///         - TRUE: device is initialized
        ///         - FALSE: device isn't initialized
        bool check_init();

    private:
        const Uint32 base_address;      /// Base address of device (IPIF)
        const Uint32 ref_clk;           /// Input clk frequency
        bool is_ready;                  /// Device is initialized and ready
        Uint32 baud_rate;               /// Current baud rate
        Uint8 baud_error;               /// Error value - baud rate assign

        /// UART baud rate setting
        /// \param bd_rate      UART baud rate to be set
        ///
        /// \return
        ///         - 0:    Baud rate correctly set
        ///         - 1:    Baud rate setting had an error
        int32 set_baud_rate(const Uint32 bd_rate);

        /// UART configuration and baud rate set
        /// \param[in]  bd_rate         UART baud rate
        ///	
        /// \return     None
        ///
        /// \note
        ///
        /// The default configuration for the UART after initialization should be:
        ///
        /// - 19,200 bps or XPAR_DFT_BAUDRATE if defined
        /// - 8 data bits
        /// - 1 stop bit
        /// - no parity
        /// - FIFO's are enabled with a receive threshold of 8 bytes
        ///
        ///   All interrupts disabled.
        void config(const Uint32 bd_rate);

        ///	Return UART base address
        ///
        /// \return     base_address value
        Uint32 get_base_address();
    };
}

#endif