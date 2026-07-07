#include <Entypes.h>
#include <Resets.h>
#include <sleep.h>
#include <xil_io.h>

namespace zusp
{
    static const Uint32 CSU_MULTI_BOOT       = 0xFFCA0010U;
    static const Uint32 CRL_APB_RESET_CTRL   = 0xFF5E0218U;
    static const Uint32 CRL_APB_RESET_REASON = 0xFF5E0220U;
    static const Uint32 CRL_WPROT            = 0xFF5E001CU;

    static const Uint32 SRST_DIS   = (1u << 0);  // disable system reset if 1
    static const Uint32 SOFT_RESET = (1u << 4);  // trigger system reset if 1

    void Resets::soft()
    {
        // Enabled writes in CRL_APB registers
        Xil_Out32(CRL_WPROT, 0u);

        // Enable reset
        Uint32 rc = Xil_In32(CRL_APB_RESET_CTRL);
        rc &= ~SRST_DIS;
        Xil_Out32(CRL_APB_RESET_CTRL, rc);

        // SOFT RESET
        sleep(1);
        Xil_Out32(CRL_APB_RESET_CTRL, rc | SOFT_RESET);
    }
}