
#ifndef IMG_HIL_H
#define IMG_HIL_H

#include <stdio.h>
#include <stdint.h>
#include <chrono>

/// Image HIL handler.
/// Manages framebuffer output and VDMA buffer preparation for the HIL system.
class Img_hil
{
public:
    /// Image HIL constructor.
    /// Initializes framebuffer and sets output resolution.
    /// \param[in] frame_ptr Pointer to the VDMA frame buffer.
    /// \param[in] width VDMA output width in pixels.
    /// \param[in] height VDMA output height in pixels.
    /// \param[in] fb_device Framebuffer device path (e.g. "/dev/fb0").
    /// \param[in] out_w Desired output resolution width (0 = keep current).
    /// \param[in] out_h Desired output resolution height (0 = keep current).
    Img_hil(void* frame_ptr, int width, int height,
            const char* fb_device = "/dev/fb0", int out_w = 0, int out_h = 0);

    /// Load and send an image frame.
    /// Reads a JPEG image, writes it to the framebuffer, and prepares
    /// the VDMA buffer for MIPI TX output.
    /// \param[in] file_name Path to the JPEG image file.
    /// \return 0 on success, 1 if image could not be loaded.
    int get_img(const char* file_name);

private:
    /// Set the framebuffer output resolution.
    /// Attempts to change the display mode via FBIOPUT_VSCREENINFO.
    /// \param[in] w Desired width in pixels.
    /// \param[in] h Desired height in pixels.
    void set_fb_resolution(int w, int h);

    int img_width;          ///< VDMA output width in pixels.
    int img_height;         ///< VDMA output height in pixels.
    void* frame_ptr;        ///< Pointer to the VDMA frame buffer.

    int out_width;          ///< Requested output resolution width.
    int out_height;         ///< Requested output resolution height.

    int fb_fd;              ///< Framebuffer file descriptor.
    uint8_t* fb_ptr;        ///< Memory-mapped framebuffer pointer.
    uint32_t fb_size;       ///< Framebuffer total size in bytes.
    uint32_t fb_width;      ///< Framebuffer visible width in pixels.
    uint32_t fb_height;     ///< Framebuffer visible height in pixels.
    uint32_t fb_stride;     ///< Framebuffer bytes per line (may differ from width * bpp/8).
    uint32_t fb_bpp;        ///< Framebuffer bits per pixel.

    int frame_count;        ///< Frame counter for FPS calculation.
    std::chrono::steady_clock::time_point t_start; ///< FPS measurement start time.
};

#endif