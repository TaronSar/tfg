///    \file CAN.cpp
///
///    \date 30 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    CAN PS class implementation.
///


#include <CAN.h>


namespace Zusp
{
    /// Set instances for null values
    CAN* CAN::CAN0 = NULL;
    CAN* CAN::CAN1 = NULL;
    
    ///	Writes a value 'register_value' in 'register_addr'
    /// \param[in]  register_addr   address of register to write on
    /// \param[in]  register_value  value to write to register
    /// \return     none
    void CAN::write_register(Uint32 register_addr,Uint32 register_value)
    {
        /// \alg
        /// <ul>
        /// <li>    Write value in register
        Hw_IO::hw_out32(register_addr, register_value);
        /// </ul>
    }

    /// Reads a value from 'register_addr'
    /// \param[in]  register_addr   address of register to read from
    /// \return	    The value read from the register.
    Uint32 CAN::read_register(Uint32 register_addr)
    {
        /// \alg
        /// <ul>
        /// <li>    Read value from register
        return Hw_IO::hw_in32(register_addr);
        /// </ul>
    }

    /// Perform a 32-bit endian conversion.
    /// \param[in] data     32-bit value to be converted
    /// \return             32-bit data with converted endianness
    Uint32 endian_swap_32(Uint32 data)
    {
        /// \alg
        /// <ul>
        /// <li>    Extract the low and high 16-bit words from the 32-bit input
        Uint16 LoWord = static_cast<Uint16>(data & inv_bits32_mask);
        Uint16 HiWord = static_cast<Uint16>((data >> value_16b) & inv_bits32_mask);

        /// <li>    Swap bytes within each 16-bit word
        LoWord = static_cast<Uint16>(((LoWord >> value_8b) & inv_bits8_mask) | 
                                        ((LoWord << value_8b) & up_16bits_mask));
        HiWord = static_cast<Uint16>(((HiWord >> value_8b) & inv_bits8_mask) | 
                                        ((HiWord << value_8b) & up_16bits_mask));

        /// <li>    Combine the swapped low and high words back into a 32-bit value
        return (static_cast<Uint32>(LoWord) << value_16b) | static_cast<Uint32>(HiWord);
        /// </ul>
    }


    /// CAN constructor
    /// \param[in]  base_addr   CAN base address
    /// \return     CAN object
    CAN::CAN(Uintptr base_addr)
    {
        /// \alg
        /// <ul>
        /// <li>    Set base address
        base_address = base_addr;

        /// <li>    CAN controller not busy
        is_busy = false;

        /// <li>    Setup Baud Rate Prescaler Register (BRPR) and Bit Timing Register
	    ///         (BTR) such that CAN baud rate equals 40Kbps, given the CAN clock
	    ///         equal to 24MHz. For more information see the CAN 2.0A, CAN 2.0B,
	    ///         ISO 11898-1 specifications.
	    set_bdr_presc(CAN_iso_prs_val);

	    set_bit_timing( CAN_iso_jw_val, CAN_iso_ts2_val,
                        CAN_iso_ts1_val);
        /// </ul>
    }


    /// CAN instance getter
    /// \param[in]  id   CAN ID for initialization
    /// \return     
    ///         - CAN instance (CAN0 or CAN1)
    ///         - NULL value
    CAN* CAN::get_CAN(CAN_id id)
    {
        /// \alg
        /// <ul>
        /// <li>    Instance set to default null
        CAN* instance = NULL;

        /// <li>    Retrieve CAN0
        if(id == CAN_0)
        {
            if(CAN0 == NULL)
            {
                /// <li>    Initialize CAN0 if not initialized
                CAN0 = new CAN(CAN0_baseaddr);
            }
            instance = CAN0;
        }
        /// <li>    Retrieve CAN1
        else if(id == CAN_1)
        {
            if(CAN1 == NULL)
            {
                /// <li>    Initialize CAN1 if not initialized
                CAN1 = new CAN(CAN1_baseaddr);
            }
            instance = CAN1;
        }

        return instance;
        /// </ul>
    }


    /// This function resets the CAN device immediately, and any pending transmission or
    /// reception is terminated at once. Both Object Layer and Transfer Layer are reset.
    /// This function does not reset the Physical Layer. TX FIFO, RX FIFO and TX High
    /// Priority Buffer are also reset.
    ///
    /// \return     none
    void CAN::reset()
    {
        /// \alg
        /// <ul>
        /// <li>    Reset of SR register
        write_register((base_address + CAN_srr_offs), CAN_srr_rs_mask);
        /// </ul>
    }


    /// This function returns status value from status Register (SR).
    ///
    /// \return     none
    Uint32 CAN::get_status()
    {
        /// \alg
        /// <ul>
        /// <li>    Get CAN SR value from register
        Uint32 status = read_register(base_address + CAN_sr_offs);
        return status;
        /// </ul>
    }


    /// This routine returns the current operation mode of the CAN device.
    ///
    /// \return
    ///     - CAN_mode_cfg if the device in Configuration Mode.
    ///     - CAN_mode_slp if the device in Sleep Mode.
    ///     - CAN_mode_nrm if the device in Normal Mode.
    ///     - CAN_mode_lbk if the device in Loop Back Mode.
    ///     - CAN_mode_snp if the device in Snoop Mode.
    Uint8 CAN::get_mode()
    {
        /// \alg
        /// <ul>
        /// <li>    Get SR status value
        Uint32 statusReg = get_status();
        Uint8 mode;

        /// <li>    There is a mode set to the CAN
        if ((statusReg & CAN_sr_cfg_mask) != 0U)
        {
            mode = static_cast<Uint8>(CAN_mode_cfg);
        }

        /// <li>    CAN is in sleep mode
        else if ((statusReg & CAN_sr_slp_mask) != 0U)
        {
            mode = static_cast<Uint8>(CAN_mode_slp);
        }

        /// <li>    CAN is in normal/snoop mode
        else if ((statusReg & CAN_sr_nrm_mask) != 0U)
        {
            if ((statusReg & CAN_sr_sn_mask) != 0U)
            {
                /// <li>    CAN is in snoop mode
                mode = static_cast<Uint8>(CAN_mode_snp);
            }
            else
            {
                /// <li>    CAN is in normal mode
                mode = static_cast<Uint8>(CAN_mode_nrm);
            }
        }

        else
        {
            /// <li>    If this line is reached, device in LB Mode.
            mode = static_cast<Uint8>(CAN_mode_lbk);
        }

        return mode;
        /// </ul>
    }


    /// This function allows the CAN device to enter one of the following operation
    /// modes:
    ///	- Configuration Mode:       Parameter CAN_mode_cfg
    ///	- Sleep Mode:               Parameter CAN_mode_slp
    ///	- Normal Mode:              Parameter CAN_mode_nrm
    ///	- Loop Back Mode:           Parameter CAN_mode_lbk.
    ///	- Snoop Mode:               Parameter CAN_mode_snp.
    ///
    /// This function does NOT ensure CAN device enters the specified mode
    /// before returning the control to the caller. The caller is responsible for
    /// checking current operation mode using CAN:get_mode().
    ///
    /// \param[in]  op_mode     Operation mode for CAN to enter
    /// \return     none
    void CAN::set_mode(Uint8 op_mode)
    {
        /// \alg
        /// <ul>
        /// <li>    Get de operation mode for CAN controller
        Uint8 current_mode = get_mode();

        /// <li>    If current mode is Normal Mode and the mode to enter is Sleep Mode,
        ///         or if current mode is Sleep Mode and the mode to enter is Normal
        ///         Mode, no transition is needed.
        if ((current_mode == static_cast<Uint8>(CAN_mode_nrm)) &&
                (op_mode == static_cast<Uint8>(CAN_mode_slp)))
        {
            /// <li>    Normal Mode ---> Sleep Mode
            write_register((base_address + CAN_msr_offs), CAN_ms_slp_mask);
        }
        else if ((current_mode == static_cast<Uint8>(CAN_mode_slp)) &&
                (op_mode == static_cast<Uint8>(CAN_mode_nrm)))
        {
            /// <li>    Sleep Mode ---> Normal Mode
            write_register((base_address + CAN_msr_offs), 0U);
        }
        else
        {
            /// <li>    If mode transition is not any of the two cases above, CAN must
            ///         enter Configuration Mode.
            write_register((base_address + CAN_srr_offs), 0U);

            /// <li>    No mode set for CAN
            if (get_mode() == static_cast<Uint8>(CAN_mode_cfg))
            {
                switch (op_mode)
                {
                    case CAN_mode_cfg:
                        /// <li>    As CAN is in Configuration Mode already.
                        ///         Nothing is needed to be done here.
                        break;

                    case CAN_mode_slp:
                        /// <li>    Write sleep mode in MSR register
                        write_register((base_address + CAN_msr_offs), CAN_ms_slp_mask);
                        /// <li>    Write sleep mode in SR register
                        write_register((base_address + CAN_srr_offs), CAN_srr_cn_mask);
                        break;

                    case CAN_mode_nrm:
                        /// <li>    Write normal mode in MSR register
                        write_register((base_address + CAN_msr_offs), 0U);
                        /// <li>    Write normal mode in SR register
                        write_register((base_address + CAN_srr_offs), CAN_srr_cn_mask);
                        break;


                    case CAN_mode_snp:
                        /// <li>    Write snoop mode in MSR register
                        write_register((base_address + CAN_msr_offs), CAN_ms_snp_mask);
                        /// <li>    Write snoop mode in SR register
                        write_register((base_address + CAN_srr_offs), CAN_srr_cn_mask);
                        break;

                    default:
                        /// <li>    Write loopback mode in MSR register
                        write_register((base_address + CAN_msr_offs), CAN_ms_lbk_mask);
                        /// <li>    Write loopback mode in SR register
                        write_register((base_address + CAN_srr_offs), CAN_srr_cn_mask);
                        break;
                }
            }
        }
        /// </ul>
    }


    /// This function reads Receive and Transmit error counters.
    ///
    /// \param[in]	rx_error_cnt    pointer to Receive Error counter data
    /// \param[in]	tx_error_cnt    pointer to Transmit Error counter data
    /// \return     none
    void CAN::get_bus_error(Uint8* rx_error_cnt, Uint8* tx_error_cnt)
    {
        /// \alg
        /// <ul>
        /// <li>    Read from error counter register
        Uint32 error_cnt = read_register(base_address + CAN_ecr_offs);

        /// <li>    Store values in parameters
        *rx_error_cnt = static_cast<Uint8>((error_cnt & CAN_ecr_rc_mask) >> CAN_ecr_rc_sft);
        *tx_error_cnt = static_cast<Uint8>(error_cnt & CAN_ecr_tc_mask);
        /// </ul>
    }
    

    /// This function reads Error status value from Error status Register (ESR).
    ///
    /// \return     ESR register value
    Uint32 CAN::get_bus_err_sts()
    {
        /// \alg
        /// <ul>
        /// <li>    Retrieve ESR register value
        Uint32 err_sts = read_register(base_address + CAN_esr_offs);
        return err_sts;
        /// </ul>
    }
    
    
    /// This function clears Error status bit(s) previously set in Error
    /// status Register (ESR). If a bit was cleared in Error status Register
    /// before this function is called, it will not be modified.
    ///
    /// \param[in]	mask    is the 32-bit mask used to clear bits in Error status
    ///		                Register.
    /// \return     none
    void CAN::clr_bus_err_sts(Uint32 mask)
    {
        /// \alg
        /// <ul>
        /// <li>    Write mask to ESR register
        write_register((base_address + CAN_esr_offs), mask);
        /// </ul>
    }


    /// Checks if the Transmission High Priority Buffer is full.
    ///
    /// \return
    ///         - FALSE: High Priority buffer is not full
    ///         - TRUE:  High Priority buffer is full
    bool CAN::is_hprior_full()
    {
        /// \alg
        /// <ul>
        /// <li>    Check if HP full bit is set in SR register
        Uint32 regValue = read_register(base_address + CAN_sr_offs);
        bool ret_val = (regValue & CAN_sr_txb_mask) != 0;
        
        return ret_val;
        /// </ul>
    }



    /// Check if the transmission FIFO is full.
    ///
    /// \return
    ///         - FALSE: Transmission FIFO is not full
    ///         - TRUE:  Transmission FIFO is full
    bool CAN::is_tx_FIFO_full()
    {
        /// \alg
        /// <ul>
        /// <li>    Read value from SR register
        Uint32 reg_value = read_register(base_address + CAN_sr_offs);

        /// <li>    Check tx FIFO bit
        bool ret_val = (reg_value & CAN_sr_tx_mask) != 0;

        return ret_val;
        /// </ul>
    }


    /// Checks if the receive FIFO is empty.
    ///
    /// \return
    ///         - FALSE: Receive FIFO is not empty
    ///         - TRUE:  Receive FIFO is empty
    bool CAN::is_rx_empty()
    {
        /// \alg
        /// <ul>
        /// <li>    Read ISR register
        Uint32 reg_value = read_register(base_address + CAN_isr_offs);

        /// <li>    Check RX FIFO Not Empty bit
        bool ret_val = (reg_value & CAN_ix_rxn_mask) == 0;
        return ret_val;
        /// </ul>
    }

    
    /// This routine returns interrupt status read from Interrupt status Register.
    ///
    /// \return     ISR register value
    Uint32 CAN::int_get_status()
    {
        /// \alg
        /// <ul>
        /// <li>    Retrieve ISR register
        Uint32 int_sts_reg = read_register(base_address + CAN_isr_offs);
        return int_sts_reg;
        /// </ul>
    }


    /// This function clears interrupt(s). Every bit set in the ISR register indicates
    /// an interrupt ocurring, and this function clears one or more interrupts by 
    /// writing a bit mask to ICR register.
    ///
    /// \param[in]	mask    is the mask to clear. Bit 1 positions will be cleared.
    ///		                Bit 0 positions won't change.
    /// \return     none
    void CAN::int_clear(Uint32 mask)
    {
        /// \alg
        /// <ul>
        Uint32 int_value;

        /// <li>    Get the ISR register value
        int_value = int_get_status();
        int_value &= mask;

        /// <li>    Clear the currently pending interrupts
        write_register(base_address +  CAN_icr_offs, int_value);
        /// </ul>
    }


    /// This function sends a CAN Frame through the CAN bus. If the TX FIFO is not full
    /// then the frame is written into the TX FIFO and otherwise, an error code is returned.
    /// This function does not wait for the frame sending.
    ///
    /// \param[in] frame_ptr    is a pointer to a 32-bit aligned buffer containing the
    ///		                    CAN frame to be sent (8-byte data).
    /// \param[in] length       length of data (between 0-8 bytes).
    /// \param[in] msg_id       message ID used for CAN protocol communication between
    ///                         devices.
    /// \return
    ///		    - 0                 TX FIFO was not full, given frame written into FIFO.
    ///		    - sts_FFO_no_room   no room in the TX FIFO for the given frame.
    ///		    - sts_device_busy   transfer is in progress.
    int32 CAN::send(Uint32* frame_ptr, Uint32 msg_id, Uint32 length)
    {
        /// \alg
        /// <ul>
        int32 status;
        Uint32 frame_id;
        Uint32 frame_dlc;
        
        /// <li>    Transfers are in progress.
        if (is_busy)
        {
            status = static_cast<int32>(sts_device_busy);
        }
        /// <li>    Transfers are not in progress.
        else
        {
            /// <li>    Check if the tx FIFO is full
            if (is_tx_FIFO_full() == true)
            {
                status = static_cast<int32>(sts_FFO_no_room);
            }
            else
            {
                /// <li>    Set the busy flag, which will be cleared after the packet
                ///         writes to FIFO.
                is_busy = true;

                /// <li>    Create message ID and DLC values
                frame_id = create_id_value(msg_id, 0U, 0U);
                frame_dlc = create_dlc_value(length);
                
                /// <li>    Write IDR, DLC, data Word 1 and data Word 2 to the CAN device.
                write_register((base_address + CAN_tFO_id_offs), frame_id);
                write_register((base_address + CAN_tFO_dl_offs), frame_dlc);
                /// <li>    Reorganize registers following endianness
                write_register((base_address + CAN_tFO_d1_offs), endian_swap_32(frame_ptr[0]));
                write_register((base_address + CAN_tFO_d2_offs), endian_swap_32(frame_ptr[1]));

                /// <li>    Clear the busy flag.
                is_busy = false;

                /// <li>    Successful sending
                status = 0;
            }
        }
            
        return status;
        /// </ul>
    }

    
    /// This function is in charge of receiving a CAN Frame. Firstly, RX FIFO is checked
    /// empty, and if not a frame from the RX FIFO is read to the buffer.
    /// An error code is returned if there is no frame.
    ///
    /// \param[in]	frame_ptr   is a pointer to a 32-bit buffer where the CAN frame is written
    /// \return
    ///		    - 0             if RX FIFO was not empty and a frame was written to the buffer
    ///		    - sts_no_data   no frame received in the buffer (RX FIFO empty, or another
    ///                         error ocurred).
    int32 CAN::receive(Uint32* frame_ptr)
    {
        /// \alg
        /// <ul>

        /// <li>    State no data received at the beginning
        int32 status = static_cast<int32>(sts_no_data);
        
        /// <li>    Check if rx FIFO is not empty
        if (is_rx_empty() == false)
        {
            /// <li>    Read ID, DLC, Data Word 1 and Data Word 2 from the CAN device.
            frame_ptr[0] = read_register(base_address + CAN_rFO_id_offs);
            frame_ptr[1] = read_register(base_address + CAN_rFO_dl_offs);
            /// <li>    Reorganize data
            frame_ptr[2] = endian_swap_32(read_register(base_address + CAN_rFO_d1_offs));
            frame_ptr[3] = endian_swap_32(read_register(base_address + CAN_rFO_d2_offs));

            /// <li>    Successful receiving
            status = 0;
            
            /// <li>    Clear RXNEMP bit in ISR. This allows future XCanPs_IsRxEmpty() call
            ///         returns correct RX FIFO occupancy/empty condition.
            int_clear(CAN_ix_rxn_mask);
        }

        return status;
        /// </ul>
    }


    /// This routine sends a CAN HP frame. Firstly, the transmit HP Buffer is checked empty.
    /// If it is, the frame is written to the corresponding buffer. If not, the method
    /// returns automatically.
    ///
    /// \param[in]	frame_ptr   is a pointer to a 32-bit buffer containing the frame to
    ///                         be sent through the bus.
    ///
    /// \return
    ///		    - 0                 if the buffer was not full and the frame was written
    ///		    - sts_FFO_no_room   if there was no space for the frame in the buffer
    ///		    - sts_device_busy   if a transfer is in progress.
    ///
    /// If immediate sending is needed, then the corresponding interrupts should
    /// be disabled.
    int32 CAN::send_hprior(Uint32* frame_ptr)
    {
        /// \alg
        /// <ul>
        int32 status;

        /// <li>    Check for transfer in progress.
        if (is_busy == true)
        {
            status = static_cast<int32>(sts_device_busy);
        }
        else
        {
            /// <li>    Check if HP buffer is full
            if (is_hprior_full() == true)
            {
                /// <li>    No space to put data
                status = static_cast<int32>(sts_FFO_no_room);
            }
            else
            {
                /// <li>    Set the busy flag for writing to FIFO.
                is_busy = true;

                /// <li>    Write IDR, DLC, Data Word 1 and Data Word 2 to the CAN device.
                write_register((base_address + CAN_HPB_id_offs), frame_ptr[0]);
                write_register((base_address + CAN_HPB_dl_offs), frame_ptr[1]);
                /// <li>    Reorganize data
                write_register((base_address + CAN_HPB_d1_offs), endian_swap_32(frame_ptr[2]));
                write_register((base_address + CAN_HPB_d2_offs), endian_swap_32(frame_ptr[3]));
                
                /// <li>    Clear the busy flag.
                is_busy = false;

                /// <li>    Successful sending
                status = 0;
            }
        }

        return status;
        /// </ul>
    }

    
    /// This routine enables acceptance filters. Up to 4 filters could be enabled.
    ///
    /// \param[in]	filter_indx     specifies which filter(s) to enable. Use
    ///		                        any AFR mask to enable one filter, and/or
    ///		                        multiple AFR mask values if multiple filters need
    ///		                        to be enabled. Filters keep their previous setting
    ///                             if not specified.
    /// \return     none
    void CAN::accept_flt_en(Uint32 filter_indx)
    {
        /// \alg
        /// <ul>
        /// <li>    Get AF register value
        Uint32 en_filters = read_register(base_address + CAN_afr_offs);

        /// <li>    Calculate new value
        en_filters |= filter_indx;
        en_filters &= static_cast<Uint32>(CAN_afr_ua_mask);

        /// <li>    Write value to AFR
        write_register((base_address +  CAN_afr_offs),en_filters);
        /// </ul>
    }


    /// This routine disables individual acceptance filters. Up to 4 filters could
    /// be disabled. If all acceptance filters are disabled then all the received
    /// frames are stored in the RX FIFO.
    ///
    /// \param[in]	filter_indx     specifies which filter(s) to disable. Filters keep
    ///                             their previous setting if not specified. If all
    ///                             acceptance filters are disabled then RX FIFO is
    ///                             filled with all received frames.
    /// \return     none
    void CAN::accept_flt_dis(Uint32 filter_indx)
    {
        /// \alg
        /// <ul>
        /// <li>    Read AF register value
        Uint32 en_filters = read_register(base_address + CAN_afr_offs);

        /// <li>    Calculate the new value and write to AFR.
        en_filters &= (Uint32)CAN_afr_ua_mask & (~filter_indx);
        write_register((base_address +  CAN_afr_offs), en_filters);
        /// </ul>
    }


    /// This function returns enabled acceptance filters. If all acceptance filters are
    /// disabled then RX FIFO is filled with all received frames.
    ///
    /// \return	The value stored in the AFR register.
    Uint32 CAN::accept_get_en()
    {
        /// \alg
        /// <ul>
        /// <li>    Retrieve AF register value
        Uint32 acc_filter_val = read_register(base_address + CAN_afr_offs);
        return acc_filter_val;
        /// </ul>
    }


    /// Checks if the CAN controller is busy or not ready for writes to the Acceptance
    /// Filter Identifier Registers (AFIR) and Acceptance Filter Mask Registers (AFMR).
    ///
    /// \return
    ///         - FALSE:    CAN device is busy
    ///         - TRUE:     CAN device is not busy
    bool CAN::is_accept_busy()
    {
        /// \alg
        /// <ul>
        /// <li>    Get SR register value
        Uint32 regValue = read_register(base_address + CAN_sr_offs);

        /// <li>    See if bit ACFBSY is established (device busy)
        bool ret_val = (regValue & CAN_sr_acf_mask) != 0;
        return ret_val;
        /// </ul>
    }


    /// This function sets values to the Acceptance Filter Mask Register (AFMR) and
    /// Acceptance Filter ID Register (AFIR) for the specified Acceptance Filter.
    ///
    /// This function should be called only after the following premises:
    ///   - The given filter is disabled by calling accept_flt_dis()
    ///   - And the CAN device is ready to accept writes to AFMR and AFIR registers,
    ///	    when is_accept_busy() returns FALSE.
    ///
    /// \param[in]	filter_indx     defines which Acceptance Filter Mask and ID Register
    ///		                        to set. Use any single AFR mask value.
    /// \param[in]	mask_val        is the value to write to the chosen AFMR.
    /// \param[in]	id_val          is the value to write to the chosen AF ID Register.
    /// \return
    ///		    - 0     if the values were set successfully.
    ///		    - 1     if given filter was not disabled, or the CAN device was not
    ///                 ready for writes to the AF specified registers.
    int32 CAN::accept_flt_set(Uint32 filter_indx, Uint32 mask_val, Uint32 id_val)
    {
        /// \alg
        /// <ul>
        Uint32 en_filters;
        int32 status;

        /// <li>    See if the given filter is currently enabled.
        en_filters = accept_get_en();
        if ((en_filters & filter_indx) == filter_indx)
        {
            /// <li>    Return an error
            status = 1;
        }
        else
        {
            /// <li>    If the CAN device is not ready for writes to AFMR and AFIR,
            ///         return an error.
            if (is_accept_busy() == true)
            {
                status = 1;
            }
            else
            {
                /// <li>    Write to the AFMR and AFIR of the specified filter.
                switch (filter_indx)
                {
                    case CAN_afr_u2_mask:
                        /// <li>    Write to AF No. 2
                        write_register((base_address + CAN_afmr2_offs), mask_val);
                        write_register((base_address + CAN_afir2_offs), id_val);
                        break;

                    case CAN_afr_u3_mask:
                        /// <li>    Write to AF No. 3
                        write_register((base_address + CAN_afmr3_offs), mask_val);
                        write_register((base_address + CAN_afir3_offs), id_val);
                        break;

                    case CAN_afr_u4_mask:
                        /// <li>    Write to AF No. 4
                        write_register((base_address + CAN_afmr4_offs), mask_val);
                        write_register((base_address + CAN_afir4_offs), id_val);
                        break;

                    default:
                        /// <li>    Write to AF No. 1
                        write_register((base_address + CAN_afmr1_offs), mask_val);
                        write_register((base_address + CAN_afir1_offs), id_val);
                        break;
                }

                /// <li>    Value set successful
                status = 0;
            }
        }
        return status;
        /// </ul>
    }


    /// This function reads the values of the AF Mask and ID Register for the specified AF.
    ///
    /// \param[in]	filter_indx     defines which AF Mask Register to get
    ///		                        Mask and ID from. Use any single filter value.
    /// \param[in]	mask_val        is a pointer to the data in which the Mask value read
    ///		                        from the chosen AF Mask Register is returned.
    /// \param[in]	id_val          is a pointer to the data in which the ID value read
    ///		                        from the chosen AF ID Register is returned.
    /// \return     none
    void CAN::accept_flt_get(Uint32 filter_indx, Uint32* mask_val, Uint32* id_val)
    {
        /// \alg
        /// <ul>
        /// <li>    Read from the AFMR and AFIR of the specified filter.
        switch (filter_indx)
        {
            case CAN_afr_u2_mask:
                /// <li>    Get value from AF No. 2
                *mask_val = read_register(base_address + CAN_afmr2_offs);
                *id_val = read_register(base_address + CAN_afir2_offs);
                break;

            case CAN_afr_u3_mask:
                /// <li>    Get value from AF No. 3
                *mask_val = read_register(base_address + CAN_afmr3_offs);
                *id_val = read_register(base_address + CAN_afir3_offs);
                break;

            case CAN_afr_u4_mask:
                /// <li>    Get value from AF No. 4
                *mask_val = read_register(base_address + CAN_afmr4_offs);
                *id_val = read_register(base_address + CAN_afir4_offs);
                break;

            default:
                /// <li>    Get value from AF No. 1
                *mask_val = read_register(base_address + CAN_afmr1_offs);
                *id_val = read_register(base_address + CAN_afir1_offs);
                break;
        }
        /// </ul>
    }


    /// This routine sets Baud Rate Prescaler value for CAN clock system. The system
    /// clock for the CAN controller is divided by (Prescaler + 1) to generate the
    /// quantum clock needed for sampling and synchronization of data.
    ///
    /// Baud Rate Prescaler can be set only if the CAN device is in Config Mode
    ///
    /// \param[in]	prescaler   is the value to set, valid from 0 to 255.
    ///
    /// \return
    ///		    - 0     if the Baud Rate prescaler value was set successfully
    ///		    - 1     if CAN device is not in Config Mode, or another error.
    int32 CAN::set_bdr_presc(Uint8 prescaler)
    {
        /// \alg
        /// <ul>
        int32 status;
        
        /// <li>    Confirm there is a mode set
        if (get_mode() != static_cast<Uint8>(CAN_mode_cfg))
        {
            /// <li>    Error
            status = 1;
        }
        else
        {
            /// <li>    Set prescaler
            write_register((base_address +  CAN_brpr_offs),
                            static_cast<Uint32>(prescaler));

            status = 0;
        }
        return status;
        /// </ul>
    }

    
    /// This routine gets Baud Rate Prescaler value for CAN clock system. The system
    /// clock for the CAN controller is divided by (Prescaler + 1) to generate the
    /// quantum clock needed for sampling and synchronization data.
    ///
    /// \return	    Current used Baud Rate Prescaler value, ranging from 0 to 255.
    Uint8 CAN::get_bdr_presc()
    {
        /// \alg
        /// <ul>
        /// <li>    Get BR prescaler value
        Uint8 read_value = static_cast<Uint8>(read_register(base_address + CAN_brpr_offs));
        return read_value;
        /// </ul>
    }


    /// This routine sets Bit time. Time segment 1, Time segment 2 and
    /// Synchronization Jump Width are set in this function. Values passed to this
    /// function must be less or equal to the actual values.
    ///
    /// Bit time can be set only if the CAN device is in Config Mode.
    /// Call set_mode() to enter Config Mode before using this function.
    ///
    /// \param[in]	jump_width      is the Synchronization Jump Width value to set.
    ///		                        From 0 to 3.
    /// \param[in]	time_segment_2  is the Time Segment 2 value to set.
    ///		                        From 0 to 7.
    /// \param[in]	time_segment_1  is the Time Segment 1 value to set.
    ///		                        From 0 to 15.
    /// \return
    ///		    - 0 if the Bit time is set successfully.
    ///		    - 1 if CAN device is not in Config Mode.
    int32 CAN::set_bit_timing(Uint8 jump_width, Uint8 time_segment_2, Uint8 time_segment_1)
    {
        /// \alg
        /// <ul>
        Uint32 Value;
        int32 status;

        /// <li>    Confirm there is a mode set
        if (get_mode() != static_cast<Uint8>(CAN_mode_cfg))
        {
            /// <li>    Error case
            status = 1;
        }
        else
        {
            /// <li>    Set value time segments
            Value = (static_cast<Uint32>(time_segment_1)) & CAN_btr_t1_mask;
            Value |= ((static_cast<Uint32>(time_segment_2)) << CAN_btr_t2_sft) & CAN_btr_t2_mask;

            /// <li>    Set syncronization jump width
            Value |= ((static_cast<Uint32>(jump_width)) << CAN_btr_sj_sft) & CAN_btr_sj_mask;

            /// <li>    Set timing
            write_register(base_address + CAN_btr_offs, Value);

            status = 0;
        }

        return status;
        /// </ul>
    }

    
    /// This routine gets Bit time. Time segment 1, Time segment 2 and
    /// Synchronization Jump Width values are read in this function. The value of each
    /// of these parameters exceeds in one to the value read.
    ///
    /// \param[in]	jump_width      stores Synchronization Jump Width value after return.
    ///                             Values from 0 to 3.
    /// \param[in]	time_segment_2  stores Time Segment 2 value after return.
    ///                             Values from 0 to 7.
    /// \param[in]	time_segment_1  stores Time Segment 1 value after return.
    ///                             Values from 0 to 15.
    /// \return     none
    void CAN::get_bit_timing(Uint8* jump_width, Uint8* time_segment_2, Uint8* time_segment_1)
    {
        /// \alg
        /// <ul>
        Uint32 value;

        /// <li>    Get bit timing register
        value = read_register(base_address + CAN_btr_offs);

        /// <li>    Store time segment and jump width values
        *time_segment_1 = static_cast<Uint8>(value & CAN_btr_t1_mask);
        *time_segment_2 = static_cast<Uint8>((value & CAN_btr_t2_mask) >> CAN_btr_t2_sft);
        *jump_width = static_cast<Uint8>((value & CAN_btr_sj_mask) >> CAN_btr_sj_sft);
        /// </ul>
    }


    /// Wait for receiving data in RX FIFO. For this method to be used, the mask
    /// CAN_ix_rxn_mask must have been used to set the corresponding receive interrupt.
    /// To set the interrupt, use the method int_enable([...]). 
    ///
    /// Used for normal mode in CAN controllers
    ///
    /// \return     none
    void CAN::wait_for_data()
    {
        /// \alg
        /// <ul>
        Uint32 rx_empty;
        
        /// <li>    Wait until the frame arrives RX FIFO via normal sending.
        do
        {
            rx_empty = read_register(base_address + CAN_isr_offs)
                                            & CAN_ix_rxn_mask;
        } while(rx_empty == 0U);
        /// </ul>
    }


    /// This routine sets the Rx Full threshold in the Watermark Interrupt Register.
    ///
    /// \param[in]	threshold   threshold to be set. Values valid from 1 to 63
    ///
    /// \return
    ///		    - 1     If the CAN device is not in Config Mode.
    ///		    - 0     If the Rx Full threshold is active in WIR register.
    ///
    /// \note		The threshold can only be set when the CAN device is in the
    ///		        config mode.
    int32 CAN::set_rx_int_wmk(Uint8 threshold)
    {
        /// \alg
        /// <ul>
        Uint32 thread_reg;
        int32 status;

        /// <li>    Confirm there is a mode set
        if (get_mode() != static_cast<Uint8>(CAN_mode_cfg))
        {
            /// <li>    Error case
            status = 1;
        }
        else
        {
            /// <li>    Get WIR register value
            thread_reg = read_register(base_address + CAN_wir_offs);

            /// <li>    Clear the Tx Empty mask
            thread_reg &= CAN_wir_e_mask;
            /// <li>    Set the Rx Full mask
            thread_reg |= (static_cast<Uint32>(threshold) & CAN_wir_f_mask);
            /// <li>    Set rx threshold
            write_register((base_address + CAN_wir_offs), thread_reg);

            status = 0;
        }
        return status;
        /// </ul>
    }


    
    /// This routine gets the Rx Full threshold from the Watermark Interrupt Register.
    ///
    /// \return	    The Rx FIFO full watermark threshold value. Values valid from 1 to 63
    Uint8 CAN::get_rx_int_wmk()
    {
        /// \alg
        /// <ul>
        /// <li>    Get threshold value and retrieve it
        Uint8 threshold = static_cast<Uint8>(
                        read_register(base_address + CAN_wir_offs) & CAN_wir_f_mask);
        return threshold;
        /// </ul>
    }


    /// This routine sets the Tx Empty threshold in the Watermark Interrupt Register.
    ///
    /// \param[in]	threshold   threshold to be set. Values valid from 1 to 63
    /// \return
    ///		- 1     If the CAN controller is not in Config Mode.
    ///		- 0     If the threshold is set in WIR
    int32 CAN::set_tx_int_wmk(Uint8 threshold)
    {
        /// \alg
        /// <ul>
        Uint32 thread_reg;
        int32 status;

        /// <li>    Confirm there is a mode set
        if(get_mode() != static_cast<Uint8>(CAN_mode_cfg))
        {
            /// <li>    Error case
            status = 1;
        }
        else
        {
            /// <li>    Get WIR value
            thread_reg = read_register(base_address + CAN_wir_offs);

            /// <li>    Set Tx Empty threshold in WIR
            thread_reg &= CAN_wir_f_mask;
            thread_reg |= (((Uint32)threshold << CAN_wir_e_shift)
                & CAN_wir_e_mask);
            write_register((base_address + CAN_wir_offs), thread_reg);

            status = 0;
        }
        
        return status;
        /// </ul>
    }


    /// This routine returns the Tx Empty threshold from WIR register.
    ///
    /// \return	    The Tx Empty FIFO threshold value. Values valid from 1 to 63.
    Uint8 CAN::get_tx_int_wmk()
    {
        /// \alg
        /// <ul>
        /// <li>    Retrieve watermark threshold
        Uint8 threshold = static_cast<Uint8>((read_register(base_address + CAN_wir_offs)
                                                & CAN_wir_e_mask) >> CAN_wir_e_shift);
        return threshold;
        /// </ul>
    }


    /// This routine returns enabled interrupt(s).
    /// 
    /// \return	    Enabled interrupt(s) in a 32-bit format.
    Uint32 CAN::int_get_enabled()
    {
        /// \alg
        /// <ul>
        /// <li>    Retrieve IER value
        Uint32 int_reg = read_register(base_address + CAN_ier_offs);
        return int_reg;
        /// </ul>
    }


    /// This routine enables interrupt(s).
    ///
    /// \param[in]	mask    is the mask to enable. Bit 1 positions will be enabled.
    ///		                Bit 0 positions will maintain the previous setting.
    /// \return     none
    void CAN::int_enable(Uint32 mask)
    {
        /// \alg
        /// <ul>
        Uint32 int_value;

        /// <li>    Get IER register value
        int_value = int_get_enabled();
        int_value |= mask;

        /// <li>    Write to the IER to enable the specified interrupts
        write_register((base_address + CAN_ier_offs), int_value);
        /// </ul>
    }


    /// This routine disables interrupt(s).
    ///
    /// \param[in]	mask    is the mask to disable. Bit 1 positions will be enabled.
    ///		                Bit 0 positions will maintain the previous setting.
    /// \return     none
    void CAN::int_disable(Uint32 mask)
    {
        /// \alg
        /// <ul>
        Uint32 int_value;

        /// <li>    Get IER register value
        int_value = int_get_enabled();
        int_value &= ~mask;

        /// <li>    Write to the IER to disable the specified interrupts
        write_register((base_address + CAN_ier_offs), int_value);
        /// </ul>
    }


    /// This method represents the interrupt handler for the CAN controller, which reads
    /// the interrupt status from the ISR, determines the source of the interrupts,
    /// calls according callbacks, and finally clears the interrupts.
    ///
    /// Application beyond this driver is responsible for providing the corresponding
    /// callbacks to handle the situations and installing these using set_handler()
    /// during initialization phase.
    ///
    /// \return     none
    void CAN::int_handler()
    {
        /// \alg
        /// <ul>
        Uint32 pending_int;
        Uint32 event_int;
        Uint32 error_sts;
        bool handler_end = false;

        /// <li>    Get ISR register value
        pending_int = int_get_status();
        /// <li>    Get enabled interrupts
        pending_int &= int_get_enabled();

        /// <li>    Clear all pending interrupts. Rising Edge interrupt
        int_clear(pending_int);

        /// <li>    An error interrupt is occurring.
        if (((pending_int & CAN_ix_err_mask) != (Uint32)0) &&
            (error_handler != NULL))
        {
            /// <li>    Handle error
            error_sts = get_bus_err_sts();
            error_handler(error_ref,error_sts);

            /// <li>    Clear Error status Register.
            clr_bus_err_sts(error_sts);
        }

        
        /// <li>    Check if any following event interrupts is pending:
        ///	        - RX FIFO Overflow
        ///	        - RX FIFO Underflow
        ///	        - TX High Priority Buffer full
        ///	        - TX FIFO Full
        ///	        - Wake up from slp mode
        ///	        - Enter slp mode
        ///	        - Enter Bus off status
        ///	        - Arbitration is lost
        event_int = pending_int & (static_cast<Uint32>(CAN_ix_rxo_mask) |
                    static_cast<Uint32>(CAN_ix_rxu_mask) |
                    static_cast<Uint32>(CAN_ix_txb_mask) |
                    static_cast<Uint32>(CAN_ix_txf_mask) |
                    static_cast<Uint32>(CAN_ix_wku_mask) |
                    static_cast<Uint32>(CAN_ix_slp_mask) |
                    static_cast<Uint32>(CAN_ix_bso_mask) |
                    static_cast<Uint32>(CAN_ix_arb_mask));

        /// <li>    If an event is ocurring
        if ((event_int != 0U) && (event_handler != NULL))
        {
            /// <li>    Handle event
            event_handler(event_ref, event_int);

            /// <li>    Bus interrupt is off
            if ((event_int & CAN_ix_bso_mask) != 0U)
            {
                /// <li>    The callback should reset the controller if "Enter
                ///         Bus Off status" interrupt occurred. All pending
                ///         interrupts are cleared and no further checking is 
                ///         needed.
                handler_end = true;
            }
        }

        if(handler_end == false)
        {
            /// <li>    This case happens when an amount of frames depending
            ///         on the RX watermark threshold are received.
            ///         And also when frame was received and is in the RX FIFO.
            if (((pending_int & (CAN_ix_rxw_mask |
                CAN_ix_rxn_mask)) != 0U) && (recv_handler != NULL))
            {
                /// <li>    'RX OK' mask is not used because the bit is set
                ///         just once even if there are multiple frames waiting
                ///         in the RX FIFO.
                ///
                /// <li>    CAN_ix_rxn_mask is used because the bit can be
                ///         set again and again automatically as long as there is
                ///         at least one frame waiting in RX FIFO.
                recv_handler(recv_ref);
            }

            /// <li>    A frame was transmitted successfully.
            if (((pending_int & (CAN_ix_txk_mask | CAN_ix_txw_mask)) != 0U) &&
                (send_handler != NULL))
            {
                send_handler(send_ref);
            }
        }
        /// </ul>
    }


    /// This routine installs an asynchronous callback function for the handler type.
    ///
    /// \param[in]	handler_type        specifies which handler to be attached.
    /// \param[in]	callback_func       is the address of the callback function.
    /// \param[in]	callback_ref        is a user data item passed to the callback  
    ///                                 function when invoked.
    ///
    /// \return
    ///		    - 0                 handler is installed.
    ///		    - sts_inv_param     handler_type is invalid.
    ///
    /// \note
    ///     If a handler was already installed, this function replaces it by a new one.
    int32 CAN::set_handler(Uint32 handler_type, void* callback_func, void* callback_ref)
    {
        /// \alg
        /// <ul>
        int32 status;
        
        /// <li>    Check handler type 
        switch (handler_type)
        {
            case CAN_hand_send:
                /// <li>    Set send handler
                send_handler =
                    (CAN_sr_handler) callback_func;
                send_ref = callback_ref;
                status = 0;
                break;

            case CAN_hand_recv:
                /// <li>    Set receive handler
                recv_handler =
                    (CAN_sr_handler) callback_func;
                recv_ref = callback_ref;
                status = 0;
                break;

            case CAN_hand_error:
                /// <li>    Set error handler
                error_handler =
                    (CAN_ev_handler) callback_func;
                error_ref = callback_ref;
                status = 0;
                break;

            case CAN_hand_event:
                /// <li>    Set event handler
                event_handler =
                    (CAN_ev_handler) callback_func;
                event_ref = callback_ref;
                status = 0;
                break;

            default:
                /// <li>    Invalid parameter passed
                status = static_cast<int32>(sts_inv_param);
                break;
        }
        return status;
        /// </ul>
    }


    /// Constructs a CAN message identifier value based on the given fields.
    ///
    /// This function employs the standard and extended message ID fields, as well as
    /// additional flags like the Remote Transmission Request (RTR) and the Substitute
    /// Remote transmission Request (SRR), to generate a complete message ID.
    /// Dominant (0) RTR values for Data Frames (sending).
    /// Recessive (1) RTR values for Remote Frames (receiving).
    ///
    /// \param[in]  rem_trans_req       Substitute RTR flag.
    /// \param[in]  rem_req_flag        RTR flag (for RTR frames).
    /// \param[in]  msg_id              ID used for message sending. 
    /// \return                 A 32-bit CAN message id that combines the previous fields.
    Uint32 CAN::create_id_value(Uint32 msg_id, Uint32 rem_trans_req, Uint32 rem_req_flag)
    {
        /// \alg
        /// <ul>
        Uint32 idValue = 0;
        bool id_extension = false;

        /// <li>    Isolate standard and extended ID values
        Uint32 standard_id = msg_id & CAN_st_id_mask;
        Uint32 extended_id = (msg_id & CAN_ex_id_mask) >> CAN_ext_shift;

        /// <li>    ID is extended
        if(extended_id != 0)
        {
            id_extension = true;
        }

        /// <li>    Combine Standard ID shifted into position, applying the mask.
        idValue |= (standard_id << CAN_id_id1_sft) & CAN_id_id1_mask;
        
        /// <li>    Combine Substitute SRR flag.
        idValue |= (rem_trans_req << CAN_id_srr_sft) & CAN_id_srr_mask;
        
        /// <li>    Combine Identifier Extension (IDE) flag.
        idValue |= (static_cast<Uint32>(id_extension) << CAN_id_ide_sft) & CAN_id_ide_mask;
        
        /// <li>    Combine Extended ID shifted into position, and applying the mask.
        idValue |= (extended_id << CAN_id_id2_sft) & CAN_id_id2_mask;
        
        /// <li>    Combine Remote Transmission Request (RTR) flag.
        idValue |= rem_req_flag & CAN_id_rtr_mask;
        
        return idValue;
        /// </ul>
    }


    /// Constructs the Data Length Code (DLC) register value from the provided DLC.
    ///
    /// This function takes a DLC value, shifts it to the corresponding position, and
    /// applies the necessary mask to generate a value to be written to the DLC register.
    ///
    /// \param[in] dlc      The DLC code (0-8 for classic CAN, up to 15 for CAN FD).
    /// \return         A 32-bit value representing the DLC that can be assigned to the DLC.
    Uint32 CAN::create_dlc_value(Uint32 dlc)
    {
        /// \alg
        /// <ul>
        /// <li>    Shift the DLC into the correct position and apply the mask.
        return (dlc << CAN_dlc_sft) & CAN_dlc_mask;
        /// </ul>
    }

}