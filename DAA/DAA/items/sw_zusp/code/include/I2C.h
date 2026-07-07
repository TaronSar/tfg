///    \file I2C.h
///
///    \date 23 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    I2C class declaration.
///


#ifndef ZUSP_I2C_H_
#define ZUSP_I2C_H_


#include <Entypes.h>
#include <Parameters.h>
#include <Hw_IO.h>
#include <Sleep.h>


namespace Zusp
{
    ///  I2C communication speed.
    typedef enum
    {
        I2C_100Khz = 0,     ///  I2C to 100KHz.
        I2C_400Khz = 1      ///  I2C to 400KHz.
    } I2C_speed;
    
    ///  Mode to set I2C controller
    typedef enum
    {
        I2C_slave,
        I2C_master
    } I2C_mode;

    ///  Direction of I2C transmission (used in master mode only)
    typedef enum
    {
        I2C_transmit,
        I2C_receive,
    } I2C_direction;

    ///  Address type used for transmission (used in master mode only)
    typedef enum
    {
        I2C_extended,
        I2C_normal,
    } I2C_address;

    ///  Slave monitoring for I2C controller (used in master mode only)
    typedef enum
    {
        I2C_mon_active,
        I2C_mon_inactive,
    } I2C_slave_mon;


    class I2C
    {
        public:
            I2C(I2C_mode md, Uint32 base_addr, I2C_speed speed);                        ///  Slave constructor
            I2C(I2C_mode md, Uint32 base_addr, I2C_slave_mon m_slave,                   ///  Master constructor
                I2C_address addr_mode, I2C_direction dir, I2C_speed speed);
            Uint32 get_speed();
            Uint8 set_speed(Uint32 frec_CLK);
            bool is_busy();                         /// I2C bus is busy
            void slave_monitor();                   /// Only avaliable for master controller
            
            void init();                            /// Start connection
            void disable();                         /// End connection

            ///  Send and receive data bytes
            void start_write(Uint32 addr, Uint32 block_size, Uint8* data);          /// Write bytes from 'data'
            void start_read(Uint32 addr, Uint32 block_size, Uint8* data);           /// Read bytes into 'data'

        private:
            Uint32 base_address;
            I2C_slave_mon mon_slave;
            I2C_address address;
            I2C_direction direction;
            I2C_mode mode;
            I2C_speed CLK_speed;
            Uint32 transfer_addr;

            ///  Initial configuration for I2C
            void reset();
            void abort_end();
            void hw_reset();
            void idr_disable();
            void clear_isr_status();
            void clear_sts_register();
            void tr_FIFO_fill(Uint8* data, Uint32 byte_count);
            Uint8 setup_master(I2C_direction direction);
            void setup_slave();
            void set_transfer_addr(Uint32 addr);
            void clear_options();
            void change_target(Uint32 addr);
            
            /// Master methods
            void master_send(Uint8* send_data, Uint32 byte_count, Uint32 slave_addr);
            void master_receive(Uint8* recv_data, Uint32 byte_count, Uint32 slave_addr);

            /// Slave methods
            void slave_send(Uint8* send_data, Uint32 byte_count, Uint32 master_addr);
            void slave_receive(Uint8* recv_data, Uint32 byte_count, Uint32 master_addr);
    };
}


#endif      ///  ZUSP_I2C_H_