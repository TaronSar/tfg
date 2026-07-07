///    \file I2C.cpp
///
///    \date 23 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    I2C class implementation.
///


#include <I2C.h>


namespace Zusp
{
    ///  ***********************************************************************************

    ///	Writes a value 'register_value' in 'register_addr'
    void write_register(Uint32 register_addr,Uint32 register_value)
    {
        Hw_IO::hw_out32(register_addr, register_value);
    }


	/// \param	register_addr 	contains the register to be read from
	/// \return	The value read from the register.
	Uint32 read_register(Uint32 register_addr)
	{
		return Hw_IO::hw_in32(register_addr);
	}


    /// Data valid to receive
    /// \return:    '1' if Rx data is valid, '0' otherwise.
    Uint32 rx_data_valid(Uint32 addr)
    {
        return ((read_register(addr + I2C_sr_offs)) & I2C_sr_RXDV);
    }


    /// Checks if Rx FIFO is full or not.
    /// \return:    '0' if Rx FIFO is full, '1' otherwise.
    Uint32 rx_FIFO_full(Uint32 addr, Uint32 count_var)
    {
        Uint32 status = 1;
        Uint32 current_count = read_register(addr + I2C_tr_offs);

        if (current_count >= (I2C_FIFO_size - (count_var % I2C_FIFO_size)))
        {
            status = 0;         /// FIFO is full
        }
        
        return status;
    }


    ///  ***********************************************************************************
    ///  Slave constructor of I2C controller
    I2C::I2C(I2C_mode md, Uint32 base_addr, I2C_speed speed)
    {
        mode = md;
        base_address = base_addr;
        CLK_speed = speed;

        ///  Reset and configure I2C controller
        reset();

        ///  Reset hardware
        hw_reset();

        /// Set speed (CLK)
        Uint8 set_CLK_result = 0;
        if(speed == I2C_100Khz)
        {
            set_CLK_result = set_speed(I2C_CLK_max_100);
        }
        else if(speed == I2C_400Khz)
        {
            set_CLK_result = set_speed(I2C_CLK_max_400);
        }

        if(set_CLK_result == 1)     /// error
        {
            ;
            /// Manage error
        }

        ///  Slave setup (I2C controller)
        setup_slave();
    }


    ///  ***********************************************************************************
    ///  Master constructor of I2C controller
    I2C::I2C(I2C_mode md, Uint32 base_addr,I2C_slave_mon m_slave, \
            I2C_address addr_mode,I2C_direction dir, I2C_speed speed)
    {
        mode = md;
        base_address = base_addr;
        address = addr_mode;
        mon_slave = m_slave;
        direction = dir;
        CLK_speed = speed;

        ///  Reset and configure I2C controller
        reset();

        ///  Reset hardware
        hw_reset();


        /// Set speed (CLK)
        Uint8 set_CLK_result = 0;
        if(speed == I2C_100Khz)
        {
            set_CLK_result = set_speed(I2C_CLK_max_100);
        }
        else if(speed == I2C_400Khz)
        {
            set_CLK_result = set_speed(I2C_CLK_max_400);
        }

        ///  Master setup
        Uint8 master_set = setup_master(direction);
        if(master_set == 1 || set_CLK_result == 1)
        {
            ///  error message/management
            ;
        }

        /// Handle slave monitoring
        slave_monitor();
    }


    ///  ************************************************************************************
    ///  Reset I2C controller configuration
    void I2C::reset()
    {
        Uint32 imr_value = read_register(base_address + I2C_isr_mask);
        
        ///  Disable interrupts
        idr_disable();

        ///  Reset configuration and clear FIFO
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        ctrl_value &= bits16_mask;
        ctrl_value |= I2C_rst_conf;
        write_register((base_address + I2C_cr_offs),ctrl_value);

        ///  Clear bits in isr status
        Uint32 isr_status = read_register(base_address + I2C_isr_offs);
        isr_status &= bits8_mask;
        write_register((base_address + I2C_isr_offs), isr_status);

        ///  Restore interrupt state
        write_register((base_address + I2C_isr_ds_offs), (I2C_isr_dis & ~(imr_value)));

        ///  Abort end
        abort_end();
    }


    ///  ************************************************************************************
    ///  Method for hardware reset on I2C controller
    void I2C::hw_reset()
    {
        ///  Disable interrupts
        idr_disable();

        ///  Clear options
        clear_options();

        ///  Clear isr status
        clear_isr_status();

        ///  Clear status register
        clear_sts_register();
    }


    ///  ************************************************************************************
    ///  Disable interrupts
    void I2C::idr_disable()
    {
        Uint32 idr_value = read_register(base_address + I2C_isr_ds_offs);
        idr_value &= bits10_mask;
        idr_value |= I2C_isr_dis;
        write_register((base_address + I2C_isr_ds_offs),idr_value);
    }


    ///  ***********************************************************************************
    ///  Clear interrupt status and CTRL hold, master enable, and acknowledge bits
    void I2C::clear_isr_status()
    {
        ///  Clear interrupt status
        Uint32 isr_value = read_register(base_address + I2C_isr_offs);
        isr_value &= bits8_mask;
        write_register(base_address + I2C_isr_offs,isr_value);


        ///  Clear hold, master enable, and acknowledge bits
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        ctrl_value &= ~(I2C_hwc_mask);
        write_register((base_address + I2C_cr_offs),ctrl_value);

        Uint32 tmt_value = read_register(base_address + I2C_tout_offs);
        tmt_value |= inv_bits8_mask;
        write_register((base_address + I2C_tout_offs),tmt_value);

        Uint32 tr_value = read_register(base_address + I2C_tr_offs);
        tr_value &= bits8_mask;
        write_register((base_address + I2C_tr_offs),tr_value);
    }
    
    
    ///  ************************************************************************************
    ///  Clear status and control registers
    void I2C::clear_sts_register()
    {
        Uint32 sts_value = read_register(base_address + I2C_sr_offs);
        write_register((base_address + I2C_sr_offs),sts_value);

        Uint32 cfg_value = read_register(base_address + I2C_cr_offs);
        cfg_value &= bits16_mask;
        write_register((base_address + I2C_cr_offs),cfg_value);
    }


    ///  ************************************************************************************
    ///  Setup master I2C controller
    Uint8 I2C::setup_master(I2C_direction direction)
    {
        Uint8 setup_master = 0;

        ///  See if HOLD bit is set (Control register)
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        bool hold_set = (ctrl_value >> I2C_ctrl_hold) & 0x1;
        if(hold_set)
        {
            bool bus_is_busy = is_busy();
            if(bus_is_busy)
            {
                setup_master = 1;
            }
        }

        ///  If bus is not busy
        if(setup_master == 0)
        {
            ///  Setup master
            ctrl_value |= I2C_set_master;
            
            if(direction == I2C_receive)
            {
                ctrl_value |= I2C_rw_master;
            }
            else    ///  Master transmitter mode
            {
                ctrl_value &= ~(I2C_rw_master);

                ///  Disable interrupts
                idr_disable();
            }
            write_register((base_address + I2C_cr_offs),ctrl_value);
        }
        

        return setup_master;
    }


    ///  ************************************************************************************
    ///  Setup slave I2C controller
    void I2C::setup_slave()
    {
        ///  Clear control register bits
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        ctrl_value &= ~(I2C_slv_clr);
        write_register((base_address + I2C_cr_offs),ctrl_value);

        ///  Disable interrupts
        idr_disable();
    }


    ///  ************************************************************************************
    ///  Manage slave monitoring (I2C master controller)
    void I2C::slave_monitor()
    {
        if(mode == I2C_master)
        {
            if(mon_slave == I2C_mon_active)      ///  Enable slave monitoring
            {
                ///  Clear transfer size register
                Uint32 tr_value = read_register(base_address + I2C_tr_offs);
                tr_value &= bits8_mask;
                write_register((base_address + I2C_tr_offs),tr_value);

                ///  Enable slave monitor mode
                Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
                ctrl_value |= I2C_slv_m_en;
                write_register((base_address + I2C_cr_offs),ctrl_value);

                ///  Initialize slave monitor register
                Uint32 sl_mon_value = read_register(base_address + I2C_slv_ps_offs);
                sl_mon_value |= I2C_slv_m_init;
                write_register((base_address + I2C_slv_ps_offs),sl_mon_value);
            }
            else                                                            ///  Disable slave monitoring
            {
                ///  Disable slave monitor mode
                Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
                ctrl_value &= ~(I2C_slv_m_dis);
                write_register((base_address + I2C_cr_offs),ctrl_value);
                
                ///  Disable slave monitor interrupt
                Uint32 ier_value = read_register(base_address + I2C_isr_en_offs);
                ier_value &= ~(I2C_slv_m_idr);
                write_register((base_address + I2C_isr_en_offs),ier_value);
            }
        }
    }


    ///  ************************************************************************************
    ///  Abort end process related to I2C reset
    void I2C::abort_end()
    {
        ///  Reset configuration
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        ctrl_value &= bits16_mask;
        write_register((base_address + I2C_cr_offs),ctrl_value);

        ///  Reset timeout
        Uint32 timeout_value = read_register(base_address + I2C_tout_offs);
        timeout_value &= bits8_mask;
        timeout_value |= I2C_tout_rst;
        write_register((base_address + I2C_tout_offs),timeout_value);

        ///  Disable interrupts
        idr_disable();
    }


    ///  ************************************************************************************
    ///  Clear options for controller
    void I2C::clear_options()
    {
        Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
        ctrl_value &= ~(I2C_slv_m_dis);
        ctrl_value & ~(I2C_hold_bit);

        if(address == I2C_normal)      ///  7-bit address
        {
            ctrl_value &= ~(I2C_nea_bit);
        }
        else        ///  10-bit address
        {
            ctrl_value |= I2C_nea_bit;
        }
        write_register((base_address + I2C_cr_offs),ctrl_value);
    }


    ///  ************************************************************************************
    ///  Set SCLK for I2C controller.
    ///  \param frec_CLK can be either 100kHz or 400kHz (most common frequencies)
    Uint8 I2C::set_speed(Uint32 frec_CLK)
    {
        Uint8 result = 0;
        
        Uint32 div_A, div_B;
        Uint32 actual_FSCL;
        Uint32 temp;
        Uint32 temp_limit;
        Uint32 last_err;
        Uint32 best_err;
        Uint32 current_err;
        Uint32 ctrl_value;
        Uint32 calc_div_A;
        Uint32 calc_div_B;
        Uint32 best_div_A;
        Uint32 best_div_B;
        Uint32 frec_Hz = frec_CLK;


        /// Assuming div_A is 0 and calculate (divisor_a+1) x (divisor_b+1).
        temp = (base_address / (I2C_CLK_divisor * frec_Hz));


        if ((temp == 0) || (frec_Hz <= 0))    /// Failure
        {
            result = 1;
        }
        else
        {
            if(frec_Hz >= I2C_CLK_max_400)
            {
                frec_Hz = I2C_CLK_max_400;
            }
            else if((frec_Hz <= I2C_CLK_max_100) && (frec_Hz > I2C_CLK_min_100))
            {
                frec_Hz = I2C_CLK_min_100;
            }

            temp_limit = ((base_address % (I2C_CLK_divisor * frec_Hz)) != 0) ? (temp + 1) : temp;
            best_err = frec_Hz;

            best_div_A = 0;
            best_div_B = 0;
            for (Uint32 t_ite = temp; t_ite <= temp_limit; t_ite++)
            {
                last_err = frec_Hz;
                calc_div_A = 0;
                calc_div_B = 0;

                for (div_B = 0; div_B < I2C_div_B_limit; div_B++)
                {
                    /// Calculate div_A based on div_B and temp
                    div_A = temp / (div_B + 1);
                    if (div_A != 0)
                    {
                        div_A = div_A - 1;
                    }

                    ///  Verify div_A range (0 to 3)
                    if (div_A <= I2C_div_A_limit)
                    {
                        ///  Calculate frequency
                        actual_FSCL = (base_address) / (I2C_CLK_divisor * (div_A + 1) * (div_B + 1));

                        ///  error calculus
                        if (actual_FSCL > frec_Hz)
                        {
                            current_err = (actual_FSCL - frec_Hz);
                        }
                        else
                        {
                            current_err = (frec_Hz - actual_FSCL);
                        }

                        ///  Update best divisors
                        if (last_err > current_err)
                        {
                            calc_div_A = div_A;
                            calc_div_B = div_B;
                            last_err = current_err;
                        }
                    }
                }

                if (last_err < best_err)
                {
                    best_err = last_err;
                    best_div_A = calc_div_A;
                    best_div_B = calc_div_B;
                }
            }

            /// Read the control register and mask the divisors
            ctrl_value = read_register(base_address + I2C_cr_offs);
            ctrl_value &= ~(I2C_div_A_mask | I2C_div_B_mask);
	        ctrl_value |= (best_div_A << I2C_div_A_shift) | (best_div_B << I2C_div_B_shift);

            write_register((base_address + I2C_cr_offs), ctrl_value);
        }

        return result;
    }


    /// ************************************************************************************
    /// Implementation of get_SCLK
    Uint32 I2C::get_speed()
    {
        Uint32 ctrl_value;
        Uint32 actual_FSCL;
        Uint32 div_A;
        Uint32 div_B;

        ctrl_value = read_register(base_address + I2C_cr_offs);

        div_A = (ctrl_value & I2C_div_A_mask) >> I2C_div_A_shift;
        div_B = (ctrl_value & I2C_div_B_mask) >> I2C_div_B_shift;

        actual_FSCL = (base_address) / (I2C_CLK_divisor * (div_A + 1) * (div_B + 1));

        return actual_FSCL;
    }


    ///  ************************************************************************************
    ///  \return     true:   BUS is busy
    ///              false:  BUS is free
    bool I2C::is_busy()
    {
        Uint32 sts_value = read_register(base_address + I2C_sr_offs);
        
        ///  Mask pin value
        bool busy = (sts_value >> I2C_bus_pin) & 0x1;
        return busy;
    }


    ///  ************************************************************************************
    ///  Set transfer address between I2C controller and connection devices
    void I2C::set_transfer_addr(Uint32 addr)
    {
        Uint32 addr_value = addr;
        addr_value &= ~(bits10_mask);
        
        Uint32 reg_value = read_register(base_address + I2C_addr_offs);
        reg_value &= ~(inv_bits10_mask);
        reg_value |= addr_value;

        ///  Write address into specific register (change only 10 first bits)
        write_register((base_address + I2C_addr_offs),reg_value);
    }


    /// ************************************************************************************
    /// \param addr:    Target of new I2C connection
    void I2C::change_target(Uint32 addr)
    {
        /// End existing connections
        disable();
        
        transfer_addr = addr;
    }


    /// ************************************************************************************
    /// Initialize connection I2C
    void I2C::init()
    {
        if(mode == I2C_master)
        {
            ///  Set address connection
            set_transfer_addr(transfer_addr);
            
            ///  Set HOLD bit (hold connection)
            Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
            ctrl_value |= I2C_hold_bit;
            write_register((base_address + I2C_cr_offs),ctrl_value);
        }
    }


    /// ************************************************************************************
    /// End connection
    void I2C::disable()
    {
        if(mode == I2C_master)
        {
            /// Clear HOLD bit connection
            Uint32 ctrl_value = read_register(base_address + I2C_cr_offs);
            ctrl_value &= ~(I2C_hold_bit);
            write_register((base_address + I2C_cr_offs),ctrl_value);

            //  Set address 0 to register (end of master-slave communication)
            set_transfer_addr(static_cast<Uint32>(0U));
        }
    }


    ///  ************************************************************************************
    ///  Writes the data bit in the data register
    void I2C::tr_FIFO_fill(Uint8* data, Uint32 byte_count)
    {
        Uint32 bytes_to_transmit = 0;
        Uint32 bytes_pending = byte_count;
        Uint32 status;
        Uint8 av_bytes;
        bool initialized = false;

        while (bytes_pending > 0)       /// Assure all bytes are sent
        {
            ///  Wait until status register TXDV bit is 0 (no data left for transmission)
            do
            {
                status = read_register(base_address + I2C_sr_offs);
            }
            while (status & I2C_sr_TXDV);

            /// Change transmission bytes value
            av_bytes = I2C_FIFO_size - read_register(base_address + I2C_tr_offs);
            
            if(av_bytes > 0)
            {
                if(bytes_pending > (static_cast<Uint32>(av_bytes)))
                {
                    bytes_to_transmit = static_cast<Uint32>(av_bytes);
                }
                else
                {
                    bytes_to_transmit = bytes_pending;
                }
                
                ///  Write data in data register
                for(Uint32 i = 0; i < bytes_to_transmit; i++)
                {
                    write_register(base_address + I2C_data_offs, static_cast<Uint32>(*data));
                    data++;
                }

                /// Update pending bytes
                bytes_pending -= bytes_to_transmit;

                if(!initialized)
                {
                    /// Initialize transmission (tell slave new data is uploaded)
                    /// Start communication
                    init();
                    initialized = true;
                }
            }
        }
    }


    ///  ************************************************************************************
    ///  Calls \function tr_FIFO_fill when the RX FIFO is not full
    void I2C::start_write(Uint32 addr, Uint32 block_size, Uint8* data)
    {
        if(mode == I2C_master)        ///  Master send
        {
            master_send(data,block_size,addr);
        }
        else                                                /// Slave send
        {
            slave_send(data,block_size,addr);
        }
    }


    ///  ************************************************************************************
    ///  Bytes receiving
    void I2C::start_read(Uint32 addr, Uint32 block_size, Uint8* data)
    {
        if(mode == I2C_master)        ///  Master receive
        {
            master_receive(data,block_size,addr);
        }
        else                                                ///  Slave receive
        {
            slave_receive(data,block_size,addr);
        }
    }


    /// ************************************************************************************
    /// Send message (I2C master controller)
    void I2C::master_send(Uint8* send_data, Uint32 byte_count, Uint32 slave_addr)
    {
        /// Setup master (sending role)
        setup_master(I2C_transmit);

        /// Transmit data through FIFO
        transfer_addr = slave_addr;
        tr_FIFO_fill(send_data,byte_count);

        /// End connection
        disable();
    }


    /// ************************************************************************************
    /// I2C controller master read data register
    void master_read(Uint32 base_addr, Uint8* recv_data, Uint32 byte_count)
    {
        Uint32 bytes_pending = byte_count;
        Uint32 max_tr_size = static_cast<Uint32>(I2C_max_tr_size);
        Uint8 value;

        while(bytes_pending > 0)
        {
            /// Wait for data to be available
            while (rx_data_valid(base_addr) == 0U)
            {
                ;
            }
            
            while((rx_data_valid(base_addr) != 0U) && bytes_pending > 0)
            {
                value = static_cast<Uint8>(read_register(base_addr + I2C_data_offs));
                *recv_data = value;
                recv_data += 1;
                bytes_pending -= 1;
            }
            
            /// Still bytes to receive
            if(bytes_pending > 0)
            {
                /// Change transmit value (update) for slave
                if (bytes_pending > max_tr_size)
                {
                    /// Wait for RXFIFO to be available
                    while(rx_FIFO_full(base_addr,max_tr_size))
                    {
                        ;
                    }
                    
                    write_register((base_addr + I2C_tr_offs),max_tr_size);
                }
                else
                {
                    /// Wait for RXFIFO to be available
                    while(rx_FIFO_full(base_addr,bytes_pending))
                    {
                        ;
                    }
                    
                    write_register((base_addr + I2C_tr_offs),bytes_pending);
                }
            }
        }
    }


    /// ************************************************************************************
    /// Receive message (I2C master controller)
    void I2C::master_receive(Uint8* recv_data, Uint32 byte_count, Uint32 slave_addr)
    {
        Uint32 max_tr_size = static_cast<Uint32>(I2C_max_tr_size);

        /// Initialize for a master receiving role.
        setup_master(I2C_receive);

        /// Setup the transfer size register so the slave knows how much
        /// to send to us.
        if (byte_count > max_tr_size)
        {
            write_register((base_address + I2C_tr_offs),max_tr_size);
        }
        else
        {
            write_register((base_address + I2C_tr_offs),byte_count);
        }

        /// Clear the interrupt status register.
        write_register((base_address + I2C_isr_offs), I2C_isr_dis);

        /// Do the address transfer to notify the slave.
        transfer_addr = slave_addr;
        init();

        /// Read data from master
        master_read(base_address,recv_data,byte_count);

        /// End connection
        disable();
    }
    

    /// ************************************************************************************
    /// Send message (I2C slave controller)
    void I2C::slave_send(Uint8* send_data, Uint32 byte_count, Uint32 master_addr)
    {
        Uint32 int_status;
        Uint32 status_reg;
        Uint32 bytes_pending = byte_count;
        Uint32 av_bytes;
        Uint32 bytes_send = 0;
        bool value;
        volatile Uint32 reg_value;
        Uint32 timeout = I2C_timeout_val;

        /// Clear the interrupt status register.
        clear_isr_status();

        /// Send data as long as there is more data to send
        value = (bytes_pending > 0);
        while (value)
        {
            /// Find out how many can be sent.
            av_bytes = I2C_FIFO_size - read_register(base_address + I2C_tr_offs);
            if (bytes_pending > av_bytes)
            {
                bytes_send = av_bytes;
            }
            else
            {
                bytes_send = bytes_pending;
            }

            for(Uint32 i = 0; i < bytes_send; i++)
            {
                write_register(base_address + I2C_data_offs, static_cast<Uint32>(*send_data));
                send_data += 1;
                bytes_pending -= 1;
            }

            /// Wait for master to read the data out of FIFO.
            do
            {
                status_reg = read_register(base_address + I2C_sr_offs);
            }
            while((status_reg & I2C_sr_TXDV) != static_cast<Uint32>(0x00U));
            value = (bytes_pending > 0);
        }

        /// Wait for transfer completion and clear the status
        while(timeout != 0U)
        {
            reg_value = read_register(base_address + I2C_isr_offs);
            if((reg_value & I2C_slv_c_mask) == I2C_slv_c_mask)
            {
                break;
            }
            Zusp::Sleep::sleep_us(I2C_timeout_val);
            timeout--;
        }

        write_register(base_address + I2C_isr_offs, reg_value);    
    }


    /// ************************************************************************************
    /// Receive message (I2C slave controller)
    void I2C::slave_receive(Uint8* recv_data, Uint32 byte_count, Uint32 master_addr)
    {
        bool recv_complete = false;
        bool master_error = false;
        Uint32 status_reg;
        Uint32 int_status;
        Uint8 value;
        Uint32 bytes_pending = byte_count;

        ///  Clear isr status and status register
        clear_isr_status();
        clear_sts_register();

        while (!recv_complete)
        {
            /// Wait for master to put data
            do
            {
                /// If master terminates the transfer before we get all
                /// the data or the master tries to read from us, it is an error.
                int_status = read_register(base_address + I2C_isr_offs);
                status_reg = read_register(base_address + I2C_sr_offs);

                if (((int_status & (I2C_slv_d_mask | I2C_slv_c_mask)) != 0x0U) &&
                    ((status_reg & I2C_sr_RXDV) == 0U))
                {
                    master_error = true;
                    break;
                }

                /// Clear the interrupt status register.
                write_register(base_address + I2C_isr_offs,int_status);
            }
            while((int_status & (I2C_slv_d_mask | I2C_slv_c_mask)) == 0x0U);

            if(master_error)
            {
                /// There was an error due to master behaviour
                break;
            }

            /// Read all data from FIFO.
            while ((status_reg & I2C_sr_RXDV) != 0x0U)
            {
                /// Receiving complete
                if ((int_status & I2C_slv_c_mask) !=0x0U)
                {
                    recv_complete = true;
                }

                /// Receive data
                value = static_cast<Uint8>(read_register(base_address + I2C_data_offs));
                *recv_data = value;
                recv_data += 1;
                bytes_pending -= 1;

                status_reg = read_register(base_address + I2C_sr_offs);
            }
        }
    }
}