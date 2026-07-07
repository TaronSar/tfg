#ifndef _UDP_SERVER_H
#define _UDP_SERVER_H

extern "C"
{
#include <xil_types.h>
#include <xemacps.h>
}

extern u8 bd_space[0x200000];

typedef u8 Ethernet_frame[71U];

struct Server_conf
{
    u8 src_mac_addr[6U]; ///< Source MAC address
    u8 dst_mac_addr[6U]; ///< Destination MAC address

    u8 src_ip_addr[4U];  ///< Source IP address
    u8 dst_ip_addr[4U];  ///< Destination IP address

    u16 src_port;        ///< Source PORT
    u16 dst_port;        ///< Destination PORT
};

template <u32 SIZE>
struct UDP_frame
{
    u8 ethernet_h[14U]; ///< Ethernet header
    u8 ip_h[20U];       ///< IP header
    u8 udp_h[8U];       ///< UDP header
    u8 payload[SIZE];   ///< Payload 
};

class UDP_server
{
public:
    UDP_server(const u32 base_addr0, const Server_conf& conf0);

    bool send(const u8* data, const u16 length);

private:
    const u32 base_addr;
    
    const Server_conf conf;

    XEmacPs emac_ps;

    Ethernet_frame rx_frame;
    Ethernet_frame tx_frame;

    u8* rx_bd_space_ptr;
    u8* tx_bd_space_ptr;

    u32 id;

    static volatile s32 frames_rx;		///< Frames have been received
    static volatile s32 frames_tx;		///< Frames have been sent
    static volatile s32 device_errors;	///< Number of errors detected in the device

    bool setup_bd();

    static void dafault_error_handler(void* callback, 
                               u8 direction, 
                               u32 error_word);

    static void dafault_send_handler(void* callback);

    static void dafault_recv_handler(void* callback);
};

#endif