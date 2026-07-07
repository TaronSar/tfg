
#ifndef VID_EMU_H
#define VID_EMU_H

#include <iostream>
#include <cstring>
#include <stdio.h>
#include <stdint.h>

/// Video emulation driver.
/// Controls AXI VDMA and MIPI TX subsystem to emulate camera output.
class Vid_emul
{
public:
    /// Video emulation constructor.
    /// Initializes VDMA channel, DMA buffer and MIPI TX subsystem.
    Vid_emul();

    /// Get pointer to the VDMA frame buffer.
    /// \return Virtual address of the DMA frame buffer, or NULL on error.
    void* get_frame_ptr();

    /// Trigger a VDMA frame transfer.
    /// Starts the VDMA and waits for frame completion IRQ.
    /// Disables MIPI path on first timeout.
    /// \return 0 on success, -1 on timeout or if MIPI path is disabled.
    int send_frame();

    /// Copy data and trigger a VDMA frame transfer.
    /// \param[in] frame_ptr Source buffer to copy into the VDMA buffer.
    /// \return 0 on success, -1 on timeout.
    int send_frame(void* frame_ptr);

private:
    bool vdma_ok = true;    ///< VDMA/MIPI path active flag.

    const uint32_t mipi_tx_ss_baseaddr = 0xA0000000; ///< MIPI TX subsystem base address.
    const uint32_t axi_vdma_baseaddr   = 0xA0010000; ///< AXI VDMA base address.

    const int frame_width  = 1280;  ///< Frame width in pixels.
    const int frame_height = 980;   ///< Frame height in pixels.

    const int mem_frame_buf_size = 64 * 1024 * 1024; ///< Total DMA buffer size (64 MB).
    const int mem_frame_num  = 4;   ///< Number of frame slots in buffer.
    const int mem_frame_size = mem_frame_buf_size / mem_frame_num; ///< Single frame size.

    /// Calculate memory offset for a given frame index.
    /// \param[in] n_frame Frame index (0-based).
    /// \return Byte offset within the DMA buffer.
    uint32_t mem_buff_offset(int n_frame);
};

#endif