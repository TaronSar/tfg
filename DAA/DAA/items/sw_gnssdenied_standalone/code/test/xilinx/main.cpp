#include "xemacps.h"
#include "xemacps_bdring.h"
#include <sleep.h>
#include <CortexA53/Cache.h>
#include <Sleep.h>

static const Uint32 ETHERNET_HEADER_SIZE = 14;
static const Uint32 IP_HEADER_SIZE = 20;
static const Uint32 UDP_HEADER_SIZE = 8;
static const Uint32 PAYLOAD_SIZE = 25;
static const Uint32 FRAME_SIZE = (ETHERNET_HEADER_SIZE + IP_HEADER_SIZE + UDP_HEADER_SIZE + PAYLOAD_SIZE);

static const Uint8 SRC_MAC_ADDR[6U] = {0x00, 0x0A, 0x35, 0x01, 0x02, 0x03};
static const Uint8 DST_MAC_ADDR[6U] = {0x04, 0x7C, 0x16, 0xA3, 0x2B, 0x56};

static const Uint8 SRC_IP_ADDR[4U] = {192, 168, 1, 10};
static const Uint8 DST_IP_ADDR[4U] = {192, 168, 1, 20};

static const Uint32 SRC_UDP_PORT = 5001;
static const Uint32 DST_UDP_PORT = 0;

static const Uint32 TXBD_CNT = 32;

Uint8 bd_space[0x200000] __attribute__ ((aligned (0x200000)));

XEmacPs emac_ps;

Uint8 frame[FRAME_SIZE];

Uint8* rx_bd_space_ptr;
Uint8* tx_bd_space_ptr;

volatile int32 frames_rx = 0;		/* Frames have been received */
volatile int32 frames_tx = 0;		/* Frames have been sent */
volatile int32 device_errors = 0;	/* Number of errors detected in the device */

void print_regs()
{
    xil_printf("XEMACPS_NWCFG_OFFSET:  %08X\n", XEmacPs_ReadReg(emac_ps.Config.BaseAddress, XEMACPS_NWCFG_OFFSET));
    xil_printf("XEMACPS_NWCTRL_OFFSET: %08X\n", XEmacPs_ReadReg(emac_ps.Config.BaseAddress, XEMACPS_NWCTRL_OFFSET));
}

int32 setup_bd()
{
    XEmacPs_Bd bd_template;
    int32 status;

    xil_printf("rx_bd_space_ptr: %lu\n", (UINTPTR)rx_bd_space_ptr);
    xil_printf("tx_bd_space_ptr: %lu\n", (UINTPTR)tx_bd_space_ptr);

    rx_bd_space_ptr = &(bd_space[0]);
	tx_bd_space_ptr = &(bd_space[0x10000]);
    
    for (u32 i = 0x10000; i < 0x20000; i++)
    {
        if ((UINTPTR) & (bd_space[i]) % 64 == 0)
        {
            xil_printf("bd_space: %lu\n", (UINTPTR)(UINTPTR) & (bd_space[i]));
            tx_bd_space_ptr = &(bd_space[i]);
            break;
        }
    }

    xil_printf("rx_bd_space_ptr: %lu\n", (UINTPTR)rx_bd_space_ptr);
    xil_printf("tx_bd_space_ptr: %lu\n", (UINTPTR)tx_bd_space_ptr);

    XEmacPs_BdClear(&bd_template);
    XEmacPs_BdSetStatus(&bd_template, XEMACPS_TXBUF_USED_MASK);

    /*
    * Create the TxBD ring
    */
    status = XEmacPs_BdRingCreate(&(XEmacPs_GetTxRing(&emac_ps)),
        (UINTPTR)tx_bd_space_ptr,
        (UINTPTR)tx_bd_space_ptr,
        XEMACPS_DMABD_MINIMUM_ALIGNMENT,
        TXBD_CNT);
    if (status != XST_SUCCESS)
    {
        xil_printf("Error setting up TxBD space, BdRingCreate(%lu)\n", status);
        return XST_FAILURE;
    }
    status = XEmacPs_BdRingClone(&(XEmacPs_GetTxRing(&emac_ps)),
        &bd_template, XEMACPS_SEND);
    if (status != XST_SUCCESS)
    {
        xil_printf("Error setting up TxBD space, BdRingClone(%lu)\n", status);
        return XST_FAILURE;
    }

    XEmacPs_SetMdioDivisor(&emac_ps, MDC_DIV_224);
    XEmacPs_SetOperatingSpeed(&emac_ps, 1000);

    return XST_SUCCESS;
}

int32 EmacPsSendFrame()
{
    for (u16 i = 0; i < FRAME_SIZE; i++)
    {
        frame[i] = 0;
    }
    int32 status;

    const Uint8* src_mac = SRC_MAC_ADDR;
    const Uint8* dst_mac = DST_MAC_ADDR;

    // memcpy(frame, dst_mac, 6);
    for (int32 i = 0; i < 6; i++)
    {
        frame[i] = dst_mac[i];
    }
    // memcpy(frame + 6, src_mac, 6);
    for (int32 i = 0; i < 6; i++)
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

    const Uint8* src_ip = SRC_IP_ADDR;
    const Uint8* dst_ip = DST_IP_ADDR;
    for (int32 i = 0; i < 4; i++)
    {
        frame[26 + i] = src_ip[i];
    }
    for (int32 i = 0; i < 4; i++)
    {
        frame[30 + i] = dst_ip[i];
    }

    // UDP Header
    u16 src_port = (SRC_UDP_PORT);
    u16 dst_port = (DST_UDP_PORT);
    for (int32 i = 0; i < 2; i++)
    {
        frame[34 + i] = ((Uint8*)&src_port)[i];
    }
    for (int32 i = 0; i < 2; i++)
    {
        frame[36 + i] = ((Uint8*)&dst_port)[i];
    }

    u16 udp_length = (UDP_HEADER_SIZE + PAYLOAD_SIZE);
    for (int32 i = 0; i < 2; i++)
    {
        frame[38 + i] = ((Uint8*)&udp_length)[i];
    }
    frame[40] = 0x00;
    frame[41] = 0x00;

    // Payload
    char payload[] = "Hello UDP, sendign frame";
    for (int32 i = 0; i < PAYLOAD_SIZE; i++)
    {
        frame[42 + i] = payload[i];
    }

    XEmacPs_BdRing* tx_ring_ptr = &XEmacPs_GetTxRing(&emac_ps);
    XEmacPs_Bd* bd_ptr;

    if (XEmacPs_BdRingAlloc(tx_ring_ptr, 1, &bd_ptr) != XST_SUCCESS)
    {
        xil_printf("Error allocating buffer descriptor\n");
        return XST_FAILURE;
    }

    XEmacPs_BdSetAddressTx(bd_ptr, (UINTPTR)&frame);
    XEmacPs_BdSetLength(bd_ptr, FRAME_SIZE);
    XEmacPs_BdClearTxUsed(bd_ptr);
    XEmacPs_BdSetLast(bd_ptr);
    // XEmacPs_BdSetStatus(bd_ptr, XEMACPS_TXBUF_USED_MASK);

    if (XEmacPs_BdRingToHw(tx_ring_ptr, 1, bd_ptr) != XST_SUCCESS)
    {
        xil_printf("Error sending buffer descriptor to Hw\n");
        return XST_FAILURE;
    }

    if ((&emac_ps)->Config.IsCacheCoherent == 0) {
		// Xil_DCacheFlushRange((UINTPTR)bd_ptr, 64);
	}

    xil_printf("UDP frame sent\n");
    return XST_SUCCESS;
}

static void XEmacPsErrorHandler(void *Callback, Uint8 Direction, u32 ErrorWord)
{
    device_errors++;
    xil_printf("XEmacPsErrorHandler: %lu", device_errors);
}

static void XEmacPsSendHandler(void *Callback)
{
	frames_tx++;
    xil_printf("XEmacPsSendHandler: %lu", frames_tx);
}

static void XEmacPsRecvHandler(void *Callback)
{
	frames_rx++;
    xil_printf("XEmacPsRecvHandler: %lu", frames_rx);
}


int main()
{
    Zusp::Dcache::disable();

    XEmacPs_Config* config;
    int32 status;

    frames_rx = 0;
    frames_tx = 0;
    device_errors = 0;

    config = XEmacPs_LookupConfig(XPAR_XEMACPS_0_DEVICE_ID);
    if (!config)
    {
        xil_printf("Error: No EMACPS config found\n");
        return XST_FAILURE;
    }

    status = XEmacPs_CfgInitialize(&emac_ps, config, config->BaseAddress);
    if (status != XST_SUCCESS)
    {
        xil_printf("Error initializing EMACPS\n");
        return XST_FAILURE;
    }

    const Uint8* mac_address = SRC_MAC_ADDR;
    XEmacPs_SetMacAddress(&emac_ps, (void *)mac_address, 1);
    xil_printf("MAC Address set.\n");

    /*
     * Setup callbacks
     */
    status = XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_DMASEND,
        (void*)XEmacPsSendHandler,
        &emac_ps);
    status |= XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_DMARECV,
        (void*)XEmacPsRecvHandler,
        &emac_ps);
    status |= XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_ERROR,
        (void*)XEmacPsErrorHandler,
        &emac_ps);
    if (status != XST_SUCCESS)
    {
        xil_printf("Error assigning handlers.\n");
        return XST_FAILURE;
    }

    status = setup_bd();
    if (status != XST_SUCCESS)
    {
        xil_printf("Failed to set up buffer descriptor.\n");
        return XST_FAILURE;
    }

    status = EmacPsSendFrame();
    if (status != XST_SUCCESS)
    {
        xil_printf("Failed to send frame.\n");
        return XST_FAILURE;
    }

    XEmacPs_SetQueuePtr(&emac_ps, (&emac_ps)->TxBdRing.BaseBdAddr, 0, XEMACPS_SEND);
    XEmacPs_Start(&emac_ps);

    print_regs();

    XEmacPs_Transmit(&emac_ps);

    xil_printf("Program finished.\n");

    return 0;
}
