#include <Multiboot.h>
#include <xil_io.h>

#include <cstdio>

namespace zusp
{
    static const Uint32 CSU_MULTI_BOOT = 0xFFCA0010U;

    void Multiboot::select(Uint8 idx)
    {
        Xil_Out32(CSU_MULTI_BOOT, idx);

        printf("MultiBoot changed to: %u\n\r", Xil_In32(CSU_MULTI_BOOT));
    }
}