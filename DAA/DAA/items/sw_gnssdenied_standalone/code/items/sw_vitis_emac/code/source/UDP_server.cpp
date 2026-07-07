#include "UDP_server.h"

extern "C" 
{
#include "sleep.h"
#include "xil_cache.h"
#include <xinterrupt_wrap.h>
#include "xparameters.h"
}

u8 bd_space[0x200000] __attribute__((aligned(0x200000)));

volatile s32 UDP_server::frames_rx = 0;
volatile s32 UDP_server::frames_tx = 0;
volatile s32 UDP_server::device_errors = 0;

UDP_server::UDP_server(const u32 base_addr0, const Server_conf& conf0) :
    base_addr(base_addr0),
    conf(conf0),
    rx_bd_space_ptr(0U),
    tx_bd_space_ptr(0U),
    id(0U)
{

    XEmacPs_Config* config = XEmacPs_LookupConfig(base_addr);

    if (!config)
    {
        xil_printf("Error: No EMACPS config found\n");
    }

    if (XEmacPs_CfgInitialize(&emac_ps, config, config->BaseAddress) != XST_SUCCESS)
    {
        xil_printf("Error initializing EMACPS\n");
    }

    XEmacPs_SetMacAddress(&emac_ps, (void*)conf.src_mac_addr, 1);

    ///< Setup callbacks
    s16 status = 0;
    status = XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_DMASEND,
        (void*)dafault_send_handler,
        &emac_ps);
    status |= XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_DMARECV,
        (void*)dafault_recv_handler,
        &emac_ps);
    status |= XEmacPs_SetHandler(&emac_ps,
        XEMACPS_HANDLER_ERROR,
        (void*)dafault_error_handler,
        &emac_ps);
    if (status != XST_SUCCESS)
    {
        xil_printf("Error assigning handlers.\n");
        status = XST_FAILURE;
    }
}

bool UDP_server::send(const u8* data, const u16 length)
{
    s32 status = 0;

    frames_rx = 0;
	frames_tx = 0;

    status = setup_bd();

    if (status != true)
    {
        xil_printf("Failed to set up buffer descriptor.\n");
        return false;
    }

    status = XSetupInterruptSystem(&emac_ps,
        (void*)(&XEmacPs_IntrHandler),
        (&emac_ps)->Config.IntrId,
        (&emac_ps)->Config.IntrParent,
        XINTERRUPT_DEFAULT_PRIORITY);

    memcpy(tx_frame, data, length);

    if ((&emac_ps)->Config.IsCacheCoherent == 0) {
		Xil_DCacheFlushRange((UINTPTR)&tx_frame, length);
	}

    XEmacPs_BdRing* TxRingPtr = &XEmacPs_GetTxRing(&emac_ps);
    XEmacPs_Bd* BdPtr;

    if (XEmacPs_BdRingAlloc(TxRingPtr, 1, &BdPtr) != XST_SUCCESS)
    {
        xil_printf("Error allocating buffer descriptor\n");
        return false;
    }

    XEmacPs_BdSetAddressTx(BdPtr, (UINTPTR)&tx_frame);
    XEmacPs_BdSetLength(BdPtr, length);
    XEmacPs_BdClearTxUsed(BdPtr);
    XEmacPs_BdSetLast(BdPtr);

    if (XEmacPs_BdRingToHw(TxRingPtr, 1, BdPtr) != XST_SUCCESS)
    {
        xil_printf("Error sending buffer descriptor to Hw\n");
        return false;
    }

    if ((&emac_ps)->Config.IsCacheCoherent == 0) {
        Xil_DCacheFlushRange((UINTPTR)BdPtr, 64);
    }

    XEmacPs_SetQueuePtr(&emac_ps, (&emac_ps)->TxBdRing.BaseBdAddr, 1, XEMACPS_SEND);
    XEmacPs_Start(&emac_ps);

    XEmacPs_Transmit(&emac_ps);

    u32 count = 0;
	while (!frames_tx) {
		count++;
		if(count == 0xFFFF)
        {
            xil_printf("ERROR: Transmission Failed!\n");
            return XST_FAILURE;
        }
		usleep(10);
	}

    if (XEmacPs_BdRingFromHwTx(&(XEmacPs_GetTxRing(&emac_ps)), 1, &BdPtr) == 0) {
		xil_printf("TxBDs were not ready for post processing\n");
		return false;
	}

	/*
	 * Examine the TxBDs.
	 *
	 * There isn't much to do. The only thing to check would be DMA
	 * exception bits. But this would also be caught in the error
	 * handler. So we just return these BDs to the free list.
	 */
	status = XEmacPs_BdRingFree(&(XEmacPs_GetTxRing(&emac_ps)),1, BdPtr);

	if (status != XST_SUCCESS) {
		xil_printf("Error freeing up TxBDs\n");
		return false;
	}

    XEmacPs_Stop(&emac_ps);

    return true;
}

bool UDP_server::setup_bd()
{
    s32 status;
    XEmacPs_Bd bd_template;

    rx_bd_space_ptr = &(bd_space[0]);
	tx_bd_space_ptr = &(bd_space[0x10000]);

    for (u32 i = 0x10000; i < 0x20000; i++)
    {
        if ((UINTPTR) & (bd_space[i]) % 64 == 0)
        {
            tx_bd_space_ptr = &(bd_space[i]);
            break;
        }
    }

    XEmacPs_BdClear(&bd_template);
    XEmacPs_BdSetStatus(&bd_template, XEMACPS_TXBUF_USED_MASK);

    /*
    * Create the TxBD ring
    */
    status = XEmacPs_BdRingCreate(&(XEmacPs_GetTxRing(&emac_ps)),
        (UINTPTR)tx_bd_space_ptr,
        (UINTPTR)tx_bd_space_ptr,
        XEMACPS_DMABD_MINIMUM_ALIGNMENT,
        32U);
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

    return true;
}

void UDP_server::dafault_error_handler(void* callback,
    u8 direction,
    u32 error_word)
{
    device_errors++;
    switch (direction)
    {
        case XEMACPS_RECV:
            if (error_word & XEMACPS_RXSR_HRESPNOK_MASK)
            {
                xil_printf("Receive DMA error: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_RXSR_RXOVR_MASK)
            {
                xil_printf("Receive over run: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_RXSR_BUFFNA_MASK)
            {
                xil_printf("Receive buffer not available: %lu\n", device_errors);
            }
        break;
        case XEMACPS_SEND:
            if (error_word & XEMACPS_TXSR_HRESPNOK_MASK)
            {
                xil_printf("Transmit DMA error: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_TXSR_URUN_MASK)
            {
                xil_printf("Transmit under run: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_TXSR_BUFEXH_MASK)
            {
                xil_printf("Transmit buffer exhausted: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_TXSR_RXOVR_MASK)
            {
                xil_printf("Transmit retry excessed limits: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_TXSR_FRAMERX_MASK)
            {
                xil_printf("Transmit collision: %lu\n", device_errors);
            }
            if (error_word & XEMACPS_TXSR_USEDREAD_MASK)
            {
                xil_printf("Transmit buffer not available: %lu\n", device_errors);
            }
        break;
    }
}

void UDP_server::dafault_send_handler(void* callback)
{
    XEmacPs* emac_ptr = (XEmacPs*)callback;

    /*
     * Disable the transmit related interrupts
     */
    XEmacPs_IntDisable(emac_ptr, (XEMACPS_IXR_TXCOMPL_MASK | XEMACPS_IXR_TX_ERR_MASK));

    frames_tx++;
    // xil_printf("XEmacPsSendHandler: %lu\n", frames_tx);
}

void UDP_server::dafault_recv_handler(void* callback)
{
    XEmacPs* emac_ptr = (XEmacPs*)callback;

    frames_rx++;
    xil_printf("XEmacPsRecvHandler: %lu\n", frames_rx);
}
