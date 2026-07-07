
/// -------------------------- ///
/// ----------BROKEN---------- ///
/// -------------------------- ///


#include <Printf.h>
#include <CortexA53/Cache.h>

#include <xemacps.h>

#define SRC_MAC_ADDR {0x00, 0x0A, 0x35, 0x01, 0x02, 0x03}
#define DST_MAC_ADDR {0x04, 0x7C, 0x16, 0xA3, 0x2B, 0x56}

#define SRC_IP_ADDR {192, 168, 1, 10}
#define DST_IP_ADDR {192, 168, 1, 20}

#define SRC_UDP_PORT 5001
#define DST_UDP_PORT 0

#define ETHERNET_HEADER_SIZE 14
#define IP_HEADER_SIZE 20
#define UDP_HEADER_SIZE 8
#define PAYLOAD_SIZE 25
#define FRAME_SIZE (ETHERNET_HEADER_SIZE + IP_HEADER_SIZE + UDP_HEADER_SIZE + PAYLOAD_SIZE)

static const Uint8 ethernet_h_sz = 14;  ///< Ethernet header size
static const Uint8 ip_h_sz = 20;        ///< IP header size
static const Uint8 upd_h_sz = 8;        ///< UPD Header size

XEmacPs EmacPsInstance;

Uint8 bd_space[0x20000] __attribute__((aligned(0x20000)));

struct UDP_server_conf
{
    Uint8 src_mac_addr[6U]; ///< Source MAC address
    Uint8 dst_mac_addr[6U]; ///< Destination MAC address

    Uint8 src_ip_addr[4U];     ///< Source IP address
    Uint8 dst_ip_addr[4U];     ///< Destination IP address

    Uint16 src_port;        ///< Source PORT
    Uint16 dst_port;        ///< Destination PORT
};

// struct UDP_address  ///< UDP address abstraction.
// {
//     static const Uint32 bdrcast_addr = 0xFFFFFFFFUL;  ///< Broadcast IP Address.

//     Uint32 ip_addr; ///< IP Address.
//     Uint16 port;    ///< UDP Port.

//     /// Build a UDP address from an IP4 and a UDP port number.
//     /// \param[in] addr IP4 address.
//     /// \param[in] port UDP port number.
//     /// \return UDP address
//     static UDP_address build(Uint32 addr, Uint16 port)
//     {
//         const UDP_address res = { addr, port };
//         return res;
//     }

//     /// Build a UDP address from an IP4 and a UDP port number.
//     /// \param[in] b3 Most  significant byte in the address.
//     /// \param[in] b2 2nd byte in the address.
//     /// \param[in] b1 3rd byte in the address.
//     /// \param[in] b0 Least significant byte in the address.
//     /// \return IP4 address as an uint32.
//     static Uint32 build_ip4_addr(Uint8 b3, Uint8 b2, Uint8 b1, Uint8 b0)
//     {
//         static const uint8_t bmask = 0xFF;
//         static const uint8_t bbits = 8;
//         uint32_t res = (b3 & bmask);
//         res <<= bbits;
//         res |= (b2 & bmask);
//         res <<= bbits;
//         res |= (b1 & bmask);
//         res <<= bbits;
//         res |= (b0 & bmask);
//         return res;
//     }
// };

class EthernetDriver
{
public:
    EthernetDriver(const UDP_server_conf& conf0) : conf(conf0)
    {
    }

    bool initialize()
    {
        XEmacPs_Config* config = XEmacPs_LookupConfig(XPAR_XEMACPS_0_DEVICE_ID);
        if (!config) return false;

        if (XEmacPs_CfgInitialize(&EmacPsInstance, config, config->BaseAddress) != XST_SUCCESS)
            return false;

        XEmacPs_SetMacAddress(&EmacPsInstance, conf.src_mac_addr, 1);

        bool ret = setup_bd();

        return ret == XST_SUCCESS;
    }

    bool sendFrame(const Uint8* data, Uint16 length)
    {
        if (length > sizeof(Frame)) return false;
        memcpy(Frame, data, length);

        XEmacPs_BdRing* TxRingPtr = &XEmacPs_GetTxRing(&EmacPsInstance);
        XEmacPs_Bd* BdPtr;

        if (XEmacPs_BdRingAlloc(TxRingPtr, 1, &BdPtr) != XST_SUCCESS)
            return false;

        XEmacPs_BdSetAddressTx(BdPtr, (UINTPTR)Frame);
        XEmacPs_BdSetLength(BdPtr, length);
        XEmacPs_BdClearTxUsed(BdPtr);
        XEmacPs_BdSetLast(BdPtr);

        if (XEmacPs_BdRingToHw(TxRingPtr, 1, BdPtr) != XST_SUCCESS)
            return false;

        XEmacPs_SetQueuePtr(&EmacPsInstance, (&EmacPsInstance)->TxBdRing.BaseBdAddr, 0, XEMACPS_SEND);
        XEmacPs_Start(&EmacPsInstance);

        XEmacPs_Transmit(&EmacPsInstance);

        return true;
    }

private:
    Uint8 Frame[FRAME_SIZE];
    UDP_server_conf conf;

    u8* RxBdSpacePtr;
    u8* TxBdSpacePtr;

    int setup_bd()
    {
        XEmacPs_Bd BdTemplate;
        int32 status;

        RxBdSpacePtr = &(bd_space[0]);
        TxBdSpacePtr = &(bd_space[0x10000]);

        for (u32 i = 0x10000; i < 0x20000; i++)
        {
            if ((UINTPTR) & (bd_space[i]) % 64 == 0)
            {
                xil_printf("bd_space: %lu\n", (UINTPTR) & (bd_space[i]));
                TxBdSpacePtr = &(bd_space[i]);
                break;
            }
        }

        XEmacPs_BdClear(&BdTemplate);
        XEmacPs_BdSetStatus(&BdTemplate, XEMACPS_TXBUF_USED_MASK);

        status = XEmacPs_BdRingCreate(&(XEmacPs_GetTxRing(&EmacPsInstance)),
            (UINTPTR)TxBdSpacePtr,
            (UINTPTR)TxBdSpacePtr,
            XEMACPS_DMABD_MINIMUM_ALIGNMENT,
            32U);

        if (status != XST_SUCCESS)
        {
            xil_printf("Error setting up TxBD space, BdRingCreate(%lu)\n", status);
            return XST_FAILURE;
        }
        status = XEmacPs_BdRingClone(&(XEmacPs_GetTxRing(&EmacPsInstance)), &BdTemplate, XEMACPS_SEND);
        if (status != XST_SUCCESS)
        {
            xil_printf("Error setting up TxBD space, BdRingClone(%lu)\n", status);
            return XST_FAILURE;
        }

        return status;
    }
};

int EmacPsSendFrame(Uint8* data)
{
    for (u16 i = 0; i < FRAME_SIZE; i++)
    {
        data[i] = 0;
    }
    int Status;

    u8 src_mac[] = SRC_MAC_ADDR;
    u8 dst_mac[] = DST_MAC_ADDR;

    // memcpy(Frame, dst_mac, 6);
    for (int i = 0; i < 6; i++)
    {
        data[i] = dst_mac[i];
    }
    // memcpy(Frame + 6, src_mac, 6);
    for (int i = 0; i < 6; i++)
    {
        data[6 + i] = src_mac[i];
    }
    data[12] = 0x08; // IPv4
    data[13] = 0x00;

    // IP Header (simplified, no checksum calculation)
    data[14] = 0x45;
    data[15] = 0x00;
    u16 total_length = (IP_HEADER_SIZE + UDP_HEADER_SIZE + PAYLOAD_SIZE);
    // memcpy(Frame + 16, &total_length, 2);
    data[16] = (total_length >> 8) & 0xFF;
    data[17] = total_length & 0xFF;

    data[18] = 0x00;
    data[19] = 0x00;
    data[20] = 0x40;
    data[21] = 0x11;
    data[22] = 0xFF;
    data[23] = 0x00;

    u8 src_ip[] = SRC_IP_ADDR;
    u8 dst_ip[] = DST_IP_ADDR;
    for (int i = 0; i < 4; i++)
    {
        data[26 + i] = src_ip[i];
    }
    for (int i = 0; i < 4; i++)
    {
        data[30 + i] = dst_ip[i];
    }

    // UDP Header
    u16 src_port = (SRC_UDP_PORT);
    u16 dst_port = (DST_UDP_PORT);
    for (int i = 0; i < 2; i++)
    {
        data[34 + i] = ((u8*)&src_port)[i];
    }
    for (int i = 0; i < 2; i++)
    {
        data[36 + i] = ((u8*)&dst_port)[i];
    }

    u16 udp_length = (UDP_HEADER_SIZE + PAYLOAD_SIZE);
    for (int i = 0; i < 2; i++)
    {
        data[38 + i] = ((u8*)&udp_length)[i];
    }
    data[40] = 0x00;
    data[41] = 0x00;

    // Payload
    char payload[] = "Hello UDP, sendign frame";
    for (int i = 0; i < PAYLOAD_SIZE; i++)
    {
        data[42 + i] = payload[i];
    }
}

int main()
{
    Zusp::Dcache::disable();

    xil_printf("Primera: 0x%x\n", &bd_space[0]);
    xil_printf("Ultima: 0x%x\n", &bd_space[0x20000]);

    UDP_server_conf conf{ DST_MAC_ADDR, DST_MAC_ADDR, SRC_IP_ADDR, DST_IP_ADDR, SRC_UDP_PORT, DST_UDP_PORT };

    EthernetDriver ed(conf);

    bool si = ed.initialize();

    if (si)
    {
        // xil_printf("EthernetDriver initialized.\n");
    }
    else
    {
        // xil_printf("ERROR. EthernetDriver not initialized.\n");
    }

    Uint8 data[FRAME_SIZE];
    EmacPsSendFrame(data);

    ed.sendFrame(data, FRAME_SIZE);

    xil_printf("Terminando...\n\n\n");

    return 0;
}