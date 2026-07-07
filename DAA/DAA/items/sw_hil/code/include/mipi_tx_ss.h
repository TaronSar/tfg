
#ifndef MIPI_TX_SS_H
#define MIPI_TX_SS_H

#include <stdio.h>
#include <stdint.h>

class Mipi_tx_ss{

public:
    Mipi_tx_ss(uint32_t baseaddr);


private:
    const uint32_t d_phy_offset = 0x1000;

    const uint32_t mipi_tx_ss_cfg = 0x00; 
    const uint32_t mipi_tx_ss_prt = 0x04;   
    const uint32_t mipi_tx_ss_gie = 0x20;
    const uint32_t mipi_tx_ss_ist = 0x24;

};

#endif