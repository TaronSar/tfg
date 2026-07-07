#include <UDP_server.h>

extern "C"
{
#include <xparameters.h>
#include "platform.h"
}

#define ETHERNET_HEADER_SIZE 14
#define IP_HEADER_SIZE 20
#define UDP_HEADER_SIZE 8
#define PAYLOAD_SIZE 25 + 4
#define FRAME_SIZE (ETHERNET_HEADER_SIZE + IP_HEADER_SIZE + UDP_HEADER_SIZE + PAYLOAD_SIZE)

#define SRC_MAC_ADDR {0x00, 0x0A, 0x35, 0x01, 0x02, 0x03}
#define DST_MAC_ADDR {0x04, 0x7C, 0x16, 0xA3, 0x2B, 0x56}

#define SRC_IP_ADDR {192, 168, 1, 10}
#define DST_IP_ADDR {192, 168, 1, 20}

#define SRC_UDP_PORT 5001
#define DST_UDP_PORT 0

u64 counter = 0;

void update_frame(u8* frame)
{
    for (u16 i = 0; i < FRAME_SIZE; i++)
    {
        frame[i] = 0;
    }

    u8 src_mac[] = SRC_MAC_ADDR;
    u8 dst_mac[] = DST_MAC_ADDR;

    // memcpy(frame, dst_mac, 6);
    for (s32 i = 0; i < 6; i++)
    {
        frame[i] = dst_mac[i];
    }
    // memcpy(frame + 6, src_mac, 6);
    for (s32 i = 0; i < 6; i++)
    {
        frame[6 + i] = src_mac[i];
    }
    frame[12] = 0x08; // IPv4
    frame[13] = 0x00;

    // IP Header (simplified, no checksum calculation)
    frame[14] = 0x45;
    frame[15] = 0x00;
    u16 total_length = (IP_HEADER_SIZE + UDP_HEADER_SIZE + PAYLOAD_SIZE);
    // memcpy(frame + 16, &total_length, 2);
    frame[16] = (total_length >> 8) & 0xFF;
    frame[17] = total_length & 0xFF;

    frame[18] = 0x00;
    frame[19] = 0x00;
    frame[20] = 0x40;
    frame[21] = 0x11;
    frame[22] = 0xFF;
    frame[23] = 0x00;

    u8 src_ip[] = SRC_IP_ADDR;
    u8 dst_ip[] = DST_IP_ADDR;
    for (s32 i = 0; i < 4; i++)
    {
        frame[26 + i] = src_ip[i];
    }
    for (s32 i = 0; i < 4; i++)
    {
        frame[30 + i] = dst_ip[i];
    }

    // UDP Header
    u8* src_port = reinterpret_cast<u8*>(SRC_UDP_PORT);
    u8* dst_port = reinterpret_cast<u8*>(DST_UDP_PORT);
    for (s32 i = 0; i < 2; i++)
    {
        frame[34 + i] = ((u8*)&src_port)[i];
    }
    for (s32 i = 0; i < 2; i++)
    {
        frame[36 + i] = ((u8*)&dst_port)[i];
    }

    u16 udp_length = (UDP_HEADER_SIZE + PAYLOAD_SIZE);
    for (s32 i = 0; i < 2; i++)
    {
        frame[38 + i] = ((u8*)&udp_length)[i];
    }
    frame[40] = 0x00;
    frame[41] = 0x00;

    // Payload
    char payload[] = "Hello UDP, sendign frame";
    for (s32 i = 0; i < PAYLOAD_SIZE - 4; i++)
    {
        frame[42 + i] = payload[i];
    }

    frame[67] = (counter >> 24) & 0xFF;
    frame[68] = (counter >> 16) & 0xFF;
    frame[69] = (counter >> 8) & 0xFF;
    frame[70] = counter & 0xFF;
}

int main()
{
    init_platform();
    print("Init app...\n\r");

    const Server_conf server_conf = {
        {0x00, 0x0A, 0x35, 0x01, 0x02, 0x03},   ///< Xilinx local MAC address
        {0x04, 0x7C, 0x16, 0xA3, 0x2B, 0x56},   ///< PC Hardware address
        {192, 168, 1, 10},                      ///< Board IP address
        {192, 168, 1, 20},                      ///< PC IP address
        5001U,                                  ///< Board PORT
        0U,                                     ///< Destination port (default 0)
    };

    UDP_server port(XPAR_XEMACPS_0_BASEADDR, server_conf);

    u8 frame[FRAME_SIZE];

    for (u32 i = 0; i < 0xFFFF; i++)
    {
        update_frame(frame);
        if (!port.send(frame, FRAME_SIZE))
        {
            xil_printf("ERROR while sending frame\n");
        }
        counter++;
    }

    print("Finished...\n");
    cleanup_platform();

    return 0;
}
