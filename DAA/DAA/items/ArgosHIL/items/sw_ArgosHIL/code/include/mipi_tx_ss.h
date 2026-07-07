
#ifndef MIPI_TX_SS_H
#define MIPI_TX_SS_H

#include <stdio.h>
#include <stdint.h>

/// MIPI CSI-2 TX Subsystem driver.
/// Provides initialization and control of the Xilinx MIPI TX IP core
/// and its associated D-PHY transmitter.
class Mipi_tx_ss
{
public:
    /// MIPI TX subsystem constructor.
    /// Performs soft reset, D-PHY initialization, and enables the core.
    /// \param[in] baseaddr Base address of the MIPI TX subsystem registers.
    Mipi_tx_ss(uint32_t baseaddr);

private:
    const uint32_t d_phy_offset   = 0x1000; ///< D-PHY register block offset.

    const uint32_t mipi_tx_ss_cfg = 0x00;   ///< Configuration register offset.
    const uint32_t mipi_tx_ss_prt = 0x04;   ///< Protocol register offset.
    const uint32_t mipi_tx_ss_gie = 0x20;   ///< Global interrupt enable offset.
    const uint32_t mipi_tx_ss_ist = 0x24;   ///< Interrupt status register offset.
};

#endif