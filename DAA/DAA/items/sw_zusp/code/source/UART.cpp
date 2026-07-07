///    \file UART.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    UART class implementation.
///


#include <UART.h>
#include <Hw_IO.h>

// Zusp::UART Zusp::UART::uart_0(115200U, 0xFF000000);
// Zusp::UART Zusp::UART::uart_1(115200U, 0xFF010000);

namespace Zusp
{
    /// Writes a value 'Register_value' in register 'base_address + Register_offs'
    /// \param[in]   base_address        UART base address
    /// \param[in]   register_offs       UART register offset
    /// \param[in]   register_value      Register value to be written on (base_address + register_offs)
    ///
    /// \return     None
    void write_register(Uint32 base_address,
                        Uint32 register_offs,
                        Uint32 register_value)
    {
        /// \alg
        /// <ul>
        /// <li>    Write register_value on (base_address + register_offs)
        Hw_IO::hw_out32((base_address) + (register_offs), (register_value));
        /// </ul>
    }


    /// Check if TX FIFO (transmission) is full
    /// \param[in]  base_address        UART base address
    ///
    /// \return
    ///         - TRUE: if the TX FIFO is full
    ///         - FALSE: if a byte can be put in FIFO.
    bool transmit_full(Uint32 base_address)
    {
        /// \alg
        /// <ul>

        /// <li>    TX full register value
        Uint32 reg_value = Hw_IO::hw_in32(base_address + UARTPS_sr_offs);

        /// <li>    Check if TX FIFO is full
        return ((reg_value & UARTPS_sr_txf) == UARTPS_sr_txf) ||
               ((reg_value & UARTPS_sr_tx_nf) == UARTPS_sr_tx_nf);
        /// </ul>
    }


    /// Check if TX FIFO (transmission) is empty
    /// \param[in]  base_address        UART base address
    ///
    /// \return
    ///         - TRUE: if the TX FIFO is empty
    ///         - FALSE: if Tx FIFO is not empty
    bool transmit_empty(Uint32 base_address)
    {
        /// \alg
        /// <ul>

        /// <li>    Check if TX FIFO is empty
        return ((Hw_IO::hw_in32((base_address)+UARTPS_sr_offs) & UARTPS_int_txe) == UARTPS_int_txe);
        /// </ul>
    }


    /// Transmission state machine is active
    ///
    /// \param[in]  base_address    UART base address
    ///
    /// \return
    ///             - TRUE: if the TX state machine is active
    ///             - FALSE: if Tx state machine is in-active
    bool transmit_active(Uint32 base_address)
    {
        /// \alg
        /// <ul>

        /// <li>    Check if TX state machine is active
        return ((Hw_IO::hw_in32((base_address) + UARTPS_sr_offs) & UARTPS_sr_tact) == UARTPS_sr_tact);
        /// </ul>
    }


    /// Read from an UART register.
    /// 
    /// \param[in]  base_address    contains the base address of the device.
    /// \param[in]  reg_offs        contains the offset from the base address of the
    ///                             device.
    ///
    /// \return The value read from the register.
    ///
    Uint32 read_register(Uint32 base_address, Uint32 reg_offs)
    {
        /// \alg
        /// <ul>
        /// <li>    Read register in position (base_address + reg_offs)
        return Hw_IO::hw_in32((base_address) + reg_offs);
        /// </ul>
    }


    /// Enable UART transmitter.
    /// \param[in]  base_address    UART base address
    ///
    /// \return     None
    void enable_UART(Uint32 base_address)
    {
        /// \alg
        /// <ul>
        /// <li>    Enable UART transmission
        Hw_IO::hw_out32((base_address + UARTPS_cr_offs),
                       ((Hw_IO::hw_in32(base_address + UARTPS_cr_offs) & (~UARTPS_end_mask)) | (UARTPS_tx_en)));
        /// </ul>
    }


    /// Disable UART transmitter.
    /// \param[in]  base_address    UART base address
    ///
    /// \return     None
    void disable_UART(Uint32 base_address)
    {
        /// \alg
        /// <ul>
        /// <li>    Disable UART transmission
        Hw_IO::hw_out32((base_address + UARTPS_cr_offs),
            (((Hw_IO::hw_in32(base_address + UARTPS_cr_offs)) & (~UARTPS_end_mask)) | (UARTPS_tx_dis)));
        /// </ul>
    }


    /// Reset of UART HW (registers and RX receiver and TX transmitter)
    /// \param[in]  base_address    UART base address
    ///
    /// \return     None
    void reset_hw(Uint32 base_address)
    {
        /// \alg
        /// <ul>

        /// <li>    Disable - interrupts
        write_register(base_address, UARTPS_idr_offs, UARTPS_ixr_mask);

        /// <li>    Disable - receive and transmit
        write_register(base_address, UARTPS_cr_offs, (UARTPS_rx_dis | UARTPS_tx_dis));

        /// <li>    Software reset of transmit. This clears the FIFO.
        write_register(base_address, UARTPS_cr_offs, (UARTPS_txrst | UARTPS_rxrst));

        /// <li>    Clear status flags - SW rst wont clear sticky flags.
        write_register(base_address, UARTPS_isr_offs, UARTPS_ixr_mask);

        /// <li>    Mode register reset value : All 0s. Normal mode, even parity, 1 stop bit
        write_register(base_address, UARTPS_mr_offs, UARTPS_ch_norm);

        /// <li>    Rx and TX trigger register rst values
        write_register(base_address, UARTPS_rxw_offs, UARTPS_rxw_rst);
        write_register(base_address, UARTPS_txw_offs, UARTPS_txw_rst);

        /// <li>    Rx timeout disabled by dft
        write_register(base_address, UARTPS_rxo_offs, UARTPS_rxo_dis);

        /// <li>    Baud rate generator and divisor reset values
        write_register(base_address, UARTPS_bdg_offs, UARTPS_bdg_rst);
        write_register(base_address, UARTPS_bdd_offs, UARTPS_bdd_rst);

        /// <li>    Control register reset value - RX and TX disabled by default
        write_register(base_address, UARTPS_cr_offs, (UARTPS_rx_dis | UARTPS_tx_dis | UARTPS_stopbrk));
        /// </ul>
    }

    /// UART constructor
    /// \param[in]  bd_rate     Baud rate used for UART initialization
    /// \param[in]  base_addr   Base address for UART instance
    ///
    /// \return     Zusp::UART instance
    UART::UART(const Uint32 base_addr, const Uint32 bd_rate) :
        base_address(base_addr),
        ref_clk(UART_clk_hz),
        is_ready(false),
        baud_rate(bd_rate),
        baud_error(0)
    {
        /// \alg
        /// <ul>
        /// <li>    UART hardware reset
        reset_hw(base_addr);

        /// <li>    Configure UART and transmitter
        config(bd_rate);
        /// </ul>
    }

    /// Method to check if the UART device is initialized
    ///
    /// \return is_ready variable
    ///             - TRUE: device is initialized
    ///             - FALSE: device isn't initialized
    bool UART::check_init()
    {
        /// \alg
        /// <ul>

        /// <li>    State UART instances
        /// <ul>
        return is_ready;
        /// </ul>
    }


    /// Data bit sending following standard Xillinx protocol.
    /// Zynq UltraScale+ TRM -- UG1085 (v2.4) -- page 609
    /// \param[in]  data    Data byte to be sent
    ///
    /// \return     None
    void UART::send_byte(const Uint8 data)
    {
        /// \alg
        /// <ul>

        /// <li>    State UART instances
        /// <ul>
        /// <li>    1. Interrupt disable
        Uint32 interrupt_disable = UARTPS_int_txe | UARTPS_sr_txf;
        write_register(base_address, UARTPS_idr_offs, interrupt_disable);

        /// <li>    2. Wait until there is enough space in TX FIFO
        while (transmit_full(base_address))
        {
            ;
        }

        /// <li>    3. Write byte into the TX FIFO
        write_register(base_address, UARTPS_ffo_offs, static_cast<Uint32>(data));

        /// <li>    4. Enable and read RX interrupts
        Uint32 interrupt_mask = read_register(base_address, UARTPS_int_offs);

        /// <li>    Enable TX_EMPTY if RX interrupts active. Retard generated to assure bit sending.
        if ((interrupt_mask & (UARTPS_sr_rxf | UARTPS_sr_rxe | UARTPS_sr_rxovr)) != 0)
        {
            write_register(base_address, UARTPS_ier_offs, UARTPS_int_txe);
        }

        /// <li>    5. Wait for previous tasks to be done
        wait_transmit_done();
        /// </ul>
    }


    /// Wait for end of transmission
    ///
    /// \return     None
    void UART::wait_transmit_done()
    {
        ///	\alg
        ///	<ul>

        /// <li>    State UART instances
        /// <ul>
        /// <li>    Wait until Transmitter FIFO is empty
        while (!transmit_empty(base_address))
        {
            ;
        }
        /// <li>    Wait until Transmitter SM is in-active
        while (transmit_active(base_address))
        {
            ;
        }
        /// </ul>
    }


    /// UART configuration and baud rate set
    /// \param[in]	bd_rate         UART baud rate
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
    void UART::config(const Uint32 bd_rate)
    {
        /// \alg
        /// <ul>

        /// <li>    State UART instances
        /// <ul>
        Uint32 mode_register;

        /// <li>    Baud rate setting and checking
        baud_error = set_baud_rate(bd_rate);
        if (baud_error == 1)
        {
            is_ready = false;
        }
        else
        {
            /// <li>    Default data format: 8 bit data, 1 stop bit, no parity
            mode_register = read_register(base_address, UARTPS_mr_offs);

            /// <li>    Mask off what's already there
            mode_register &= (~(UARTPS_chl_mask |
                                UARTPS_stp_mask |
                                UARTPS_ffo_mask |
                                UARTPS_par_mask));

            /// <li>    Set the register value to desired data format
            mode_register |= (UARTPS_chl_8 |
                              UARTPS_stp_1 |
                              UARTPS_ffo_B |
                              UARTPS_p_none);

            /// <li>    Write out mode register
            write_register(base_address, UARTPS_mr_offs, mode_register);

            /// <li>    Set the RX FIFO trigger at 8 data bytes. 
            write_register(base_address, UARTPS_rxw_offs, rxfifo_data_B);

            /// <li>    Set the RX timeout to 1, which will be 4 character time 
            write_register(base_address, UARTPS_rxo_offs, rxfifo_tout_dft);

            /// <li>    Disable all interrupts, polled mode is the default
            write_register(base_address, UARTPS_idr_offs, UARTPS_ixr_mask);


            is_ready = true;
        }
        /// </ul>
    }


    /// UART baud rate setting
    /// \param bd_rate      UART baud rate to be set
    ///
    /// \return
    ///         - 0:    Baud rate correctly set
    ///         - 1:    Baud rate setting had an error
    int32 UART::set_baud_rate(const Uint32 bd_rate)
    {
        /// \alg
        /// <ul>
        Uint32 calc_baud_rate;
        Uint32 baud_err;
        Uint32 best_error = UINT32_MAX;
        Uint32 best_BRGR = 0;
        Uint32 best_bauddiv = 0;
        Uint32 mode_reg;
        Uint32 input_clk;

        int32 set_bdr_val = 1;

        /// <li>    If the baud rate is not too high
        if ((bd_rate <= UARTPS_max_rt) && (bd_rate >= UARTPS_min_rt))
        {
            /// <li>    Read the mode register and calculate input
            ///         CLK value
            mode_reg = read_register(base_address, UARTPS_mr_offs);
            input_clk = ref_clk;

            if (mode_reg & UARTPS_clksel)
            {
                /// <li>    CLK is 8-bit alligned
                input_clk /= min_clk_div;
            }

            for (Uint32 iter_baud_div = 4U; iter_baud_div < 255U; iter_baud_div++)
            {
                Uint32 div_int = input_clk / (bd_rate * (iter_baud_div + 1));
                Uint32 calc_baud_rate = input_clk / (div_int * (iter_baud_div + 1));

                baud_err = (bd_rate > calc_baud_rate) ? (bd_rate - calc_baud_rate) : (calc_baud_rate - bd_rate);

                /// <li>    Update best values
                if (baud_err < best_error)
                {
                    best_BRGR = div_int;
                    best_bauddiv = iter_baud_div;
                    best_error = baud_err;
                }
            }
            
            /// <li>    Calculate error percentage
            Real percent_error = (static_cast<Real>(best_error) * percent) / bd_rate;

            /// <li>    If the error percentage is less than
            ///         the maximum allowed
            if (percent_error <= UARTPS_bde_rt)
            {
                disable_UART(base_address);

                write_register(base_address, UARTPS_bdg_offs, best_BRGR);
                write_register(base_address, UARTPS_bdd_offs, best_bauddiv);

                write_register(base_address, UARTPS_cr_offs, UARTPS_txrst | UARTPS_rxrst);


                enable_UART(base_address);

                baud_rate = bd_rate;

                /// <li>    Setting correctly done
                set_bdr_val = 0;
            }
        }

        return set_bdr_val;
        /// </ul>
    }


    /// Return UART base address
    ///
    /// \return     base_address value
    Uint32 UART::get_base_address()
    {
        /// \alg
        /// <ul>
        /// <li>    Return UART base address
        return base_address;
        /// </ul>
    }

}