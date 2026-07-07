///    \file CAN.h
///
///    \date 30 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    CAN PS class declaration.
///


#include <Entypes.h>
#include <Core_def.h>
#include <Hw_IO.h>
#include <Parameters.h>


namespace Zusp
{
    /// Definition of pointer to function CAN_sr_handler (send-receive)
    /// Used for handling CAN interrupt events, where each handler 
    /// takes a generic pointer (void*) as a reference to additional data or context.
    /// This is an efficient way of managing interrupt callbacks for CAN events.
    typedef void (*CAN_sr_handler)(void* ref);

    /// Definition of pointer to function CAN_ev_handler (errors and events)
    /// used to define the structure of callbacks that handle both CAN error and
    /// event interrupts. It allows the upper layer to pass in a reference and an
    /// error or event mask, which the callback function uses to respond to specific
    /// interrupt conditions.
    typedef void (*CAN_ev_handler)(void* ref, Uint32 mask);

    /// CAN ID for instances
    typedef enum
    {
        CAN_0,
        CAN_1
    } CAN_id;
    
    /// CAN PS class implementation
    class CAN
    {
        public:
            /// CAN instance getter
            /// \param[in]  id   CAN ID for initialization
            /// \return     
            ///         - CAN instance (CAN0 or CAN1)
            ///         - NULL value
            static CAN* get_CAN(CAN_id id);

            /// This function resets the CAN device immediately, and any pending transmission or
            /// reception is terminated at once. Both Object Layer and Transfer Layer are reset.
            /// This function does not reset the Physical Layer. TX FIFO, RX FIFO and TX High
            /// Priority Buffer are also reset.
            ///
            /// \return     none
            void reset();

            /// This routine returns the current operation mode of the CAN device.
            ///
            /// \return
            ///     - CAN_mode_cfg if the device in Configuration Mode.
            ///     - CAN_mode_slp if the device in Sleep Mode.
            ///     - CAN_mode_nrm if the device in Normal Mode.
            ///     - CAN_mode_lbk if the device in Loop Back Mode.
            ///     - CAN_mode_snp if the device in Snoop Mode.
            Uint8 get_mode();

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
            void set_mode(Uint8 op_mode);

            /// This function clears Error status bit(s) previously set in Error
            /// status Register (ESR). If a bit was cleared in Error status Register
            /// before this function is called, it will not be modified.
            ///
            /// \param[in]	mask    is the 32-bit mask used to clear bits in Error status
            ///		                Register.
            /// \return     none
            void clr_bus_err_sts(Uint32 mask);

            /// This function reads Receive and Transmit error counters.
            ///
            /// \param[in]	rx_error_cnt    pointer to Receive Error counter data
            /// \param[in]	tx_error_cnt    pointer to Transmit Error counter data
            /// \return     none
            void get_bus_error(Uint8* rx_error_cnt, Uint8* tx_error_cnt);

            /// This function reads Error status value from Error status Register (ESR).
            /// \return     ESR register value
            Uint32 get_bus_err_sts();

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
            int32 send(Uint32* frame_ptr, Uint32 msg_id, Uint32 length);

            /// This function is in charge of receiving a CAN Frame. Firstly, RX FIFO is checked
            /// empty, and if not a frame from the RX FIFO is read to the buffer.
            /// An error code is returned if there is no frame.
            ///
            /// \param[in]	frame_ptr   is a pointer to a 32-bit buffer where the CAN frame is written
            /// \return
            ///		    - 0             if RX FIFO was not empty and a frame was written to the buffer
            ///		    - xst_no_data   no frame received in the buffer (RX FIFO empty, or another
            ///                         error ocurred).
            int32 receive(Uint32* frame_ptr);


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
            int32 set_bdr_presc(Uint8 prescaler);

            /// This routine gets Baud Rate Prescaler value for CAN clock system. The system
            /// clock for the CAN controller is divided by (Prescaler + 1) to generate the
            /// quantum clock needed for sampling and synchronization data.
            ///
            /// \return	    Current used Baud Rate Prescaler value, ranging from 0 to 255.
            Uint8 get_bdr_presc();

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
            int32 set_bit_timing(Uint8 jump_width, Uint8 time_segment_2, Uint8 time_segment_1);

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
            void get_bit_timing(Uint8* jump_width, Uint8* time_segment_2, Uint8* time_segment_1);

            /// Wait for receiving data in RX FIFO. For this method to be used, the mask
            /// CAN_ix_rxn_mask must have been used to set the corresponding receive interrupt.
            /// To set the interrupt, use the method int_enable([...]). 
            ///
            /// Used for normal mode in CAN controllers
            /// \return     none
            void wait_for_data();

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
            int32 set_rx_int_wmk(Uint8 threshold);

            /// This routine gets the Rx Full threshold from the Watermark Interrupt Register.
            ///
            /// \return	    The Rx FIFO full watermark threshold value. Values valid from 1 to 63
            Uint8 get_rx_int_wmk();

            /// This routine sets the Tx Empty threshold in the Watermark Interrupt Register.
            ///
            /// \param[in]	threshold   threshold to be set. Values valid from 1 to 63
            /// \return
            ///		- 1     If the CAN controller is not in Config Mode.
            ///		- 0     If the threshold is set in WIR
            int32 set_tx_int_wmk(Uint8 threshold);

            /// This routine returns the Tx Empty threshold from WIR register.
            ///
            /// \return	    The Tx Empty FIFO threshold value. Values valid from 1 to 63.
            Uint8 get_tx_int_wmk();

            /// This routine returns enabled interrupt(s).
            /// 
            /// \return	    Enabled interrupt(s) in a 32-bit format.
            Uint32 int_get_enabled();

            /// This routine enables interrupt(s).
            ///
            /// \param[in]	mask    is the mask to enable. Bit 1 positions will be enabled.
            ///		                Bit 0 positions will maintain the previous setting.
            /// \return     none
            void int_enable(Uint32 mask);

            /// This routine disables interrupt(s).
            ///
            /// \param[in]	mask    is the mask to disable. Bit 1 positions will be enabled.
            ///		                Bit 0 positions will maintain the previous setting.
            /// \return     none
            void int_disable(Uint32 mask);

        private:
            /// Proper class attributes
            Uintptr base_address;
            bool is_busy;

            void* send_ref;
            void* recv_ref;
            void* error_ref;
            void* event_ref;

            /// Interrupt handlers
            CAN_sr_handler send_handler;
            CAN_sr_handler recv_handler;
            CAN_ev_handler error_handler;
            CAN_ev_handler event_handler;

            /// Private CAN instances
            static CAN* CAN0;
            static CAN* CAN1;

            /// CAN constructor
            /// \param[in]  base_addr   CAN base address
            /// \return     CAN object
            CAN(Uintptr base_addr);

            /// This function returns status value from status Register (SR).
            /// \return     none
            Uint32 get_status();

            /// This routine returns interrupt status read from Interrupt status Register.
            /// \return     ISR register value
            Uint32 int_get_status();

            /// Checks if the Transmission High Priority Buffer is full.
            /// \return
            ///         - FALSE: High Priority buffer is not full
            ///         - TRUE:  High Priority buffer is full
            bool is_hprior_full();

            /// Check if the transmission FIFO is full.
            /// \return
            ///         - FALSE: Transmission FIFO is not full
            ///         - TRUE:  Transmission FIFO is full
            bool is_tx_FIFO_full();

            /// Checks if the receive FIFO is empty.
            /// \return
            ///         - FALSE: Receive FIFO is not empty
            ///         - TRUE:  Receive FIFO is empty
            bool is_rx_empty();

            /// This function clears interrupt(s). Every bit set in the ISR register indicates
            /// an interrupt ocurring, and this function clears one or more interrupts by 
            /// writing a bit mask to ICR register.
            ///
            /// \param[in]	mask    is the mask to clear. Bit 1 positions will be cleared.
            ///		                Bit 0 positions won't change.
            /// \return     none
            void int_clear(Uint32 mask);

            /// This routine sends a CAN HP frame. Firstly, the transmit HP Buffer is checked empty.
            /// If it is, the frame is written to the corresponding buffer. If not, the method
            /// returns automatically.
            ///
            /// \param[in]	frame_ptr   is a pointer to a 32-bit buffer containing the frame to
            ///                         be sent through the bus.
            ///
            /// \return
            ///		    - 0                 if the buffer was not full and the frame was written
            ///		    - xst_FFO_no_room   if there was no space for the frame in the buffer
            ///		    - xst_device_busy   if a transfer is in progress.
            ///
            /// If immediate sending is needed, then the corresponding interrupts should
            /// be disabled.
            int32 send_hprior(Uint32* frame_ptr);

            /// This routine enables acceptance filters. Up to 4 filters could be enabled.
            ///
            /// \param[in]	filter_indx     specifies which filter(s) to enable. Use
            ///		                        any AFR mask to enable one filter, and/or
            ///		                        multiple AFR mask values if multiple filters need
            ///		                        to be enabled. Filters keep their previous setting
            ///                             if not specified.
            /// \return     none
            void accept_flt_en(Uint32 filter_indx);

            /// This routine disables individual acceptance filters. Up to 4 filters could
            /// be disabled. If all acceptance filters are disabled then all the received
            /// frames are stored in the RX FIFO.
            ///
            /// \param[in]	filter_indx     specifies which filter(s) to disable. Filters keep
            ///                             their previous setting if not specified. If all
            ///                             acceptance filters are disabled then RX FIFO is
            ///                             filled with all received frames.
            /// \return     none
            void accept_flt_dis(Uint32 filter_indx);

            /// This function returns enabled acceptance filters. If all acceptance filters are
            /// disabled then RX FIFO is filled with all received frames.
            ///
            /// \return	The value stored in the AFR register.
            Uint32 accept_get_en();

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
            int32 accept_flt_set(Uint32 filter_indx, Uint32 mask_val, Uint32 id_val);

            /// Checks if the CAN controller is busy or not ready for writes to the Acceptance
            /// Filter Identifier Registers (AFIR) and Acceptance Filter Mask Registers (AFMR).
            ///
            /// \return
            ///         - FALSE:    CAN device is busy
            ///         - TRUE:     CAN device is not busy
            bool is_accept_busy();

            /// This function reads the values of the AF Mask and ID Register for the specified AF.
            ///
            /// \param[in]	filter_indx     defines which AF Mask Register to get
            ///		                        Mask and ID from. Use any single filter value.
            /// \param[in]	mask_val        is a pointer to the data in which the Mask value read
            ///		                        from the chosen AF Mask Register is returned.
            /// \param[in]	id_val          is a pointer to the data in which the ID value read
            ///		                        from the chosen AF ID Register is returned.
            /// \return     none
            void accept_flt_get(Uint32 filter_indx, Uint32* mask_val, Uint32* id_val);

            /// This method represents the interrupt handler for the CAN controller, which reads
            /// the interrupt status from the ISR, determines the source of the interrupts,
            /// calls according callbacks, and finally clears the interrupts.
            ///
            /// Application beyond this driver is responsible for providing the corresponding
            /// callbacks to handle the situations and installing these using set_handler()
            /// during initialization phase.
            ///
            /// \return     none
            void int_handler();

            /// This routine installs an asynchronous callback function for the handler type.
            ///
            /// \param[in]	handler_type        specifies which handler to be attached.
            /// \param[in]	callback_func       is the address of the callback function.
            /// \param[in]	callback_ref        is a user data item passed to the callback  
            ///                                 function when invoked.
            ///
            /// \return
            ///		    - 0                 handler is installed.
            ///		    - xst_inv_param     handler_type is invalid.
            ///
            /// \note
            ///     If a handler was already installed, this function replaces it by a new one.
            int32 set_handler(Uint32 handler_type, void* callback_func, void* callback_ref);

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
            static Uint32 create_id_value(Uint32 msg_id, Uint32 rem_trans_req, Uint32 rem_req_flag);

            /// Constructs the Data Length Code (DLC) register value from the provided DLC.
            ///
            /// This function takes a DLC value, shifts it to the corresponding position, and
            /// applies the necessary mask to generate a value to be written to the DLC register.
            ///
            /// \param[in] dlc      The DLC code (0-8 for classic CAN, up to 15 for CAN FD).
            /// \return         A 32-bit value representing the DLC that can be assigned to the DLC.
            static Uint32 create_dlc_value(Uint32 dlc);

            ///	Writes a value 'register_value' in 'register_addr'
            /// \param[in]  register_addr   address of register to write on
            /// \param[in]  register_value  value to write to register
            /// \return     none
            void write_register(Uint32 register_addr,Uint32 register_value);

            /// Reads a value from 'register_addr'
            /// \param[in]  register_addr   address of register to read from
            /// \return	    The value read from the register.
            Uint32 read_register(Uint32 register_addr);
    };
}