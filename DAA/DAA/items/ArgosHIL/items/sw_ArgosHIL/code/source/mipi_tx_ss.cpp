#include <mipi_tx_ss.h>

extern "C" {
    #include <memmap.h>
}

static void set_reg(uint32_t addr, uint32_t val);
static void get_reg(uint32_t addr, uint32_t *val);


Mipi_tx_ss::Mipi_tx_ss(uint32_t baseaddr)
{
    
    uint32_t ready;

    /// Disable global interrupt enable
    set_reg(baseaddr + mipi_tx_ss_gie, 0x0000);
    /// Clear pending interrupt status flags
    set_reg(baseaddr + mipi_tx_ss_ist, 0x003F);
    /// Assert soft reset
    set_reg(baseaddr + mipi_tx_ss_cfg, 0x0002);

    /// Reset and release D-PHY
    set_reg(baseaddr + d_phy_offset, 0x0);
    set_reg(baseaddr + d_phy_offset, 0x1);
    
    /// Enable line start/end packet generation
    set_reg(baseaddr + mipi_tx_ss_prt, 0x8000);

    /// Re-enable global interrupts
    set_reg(baseaddr + mipi_tx_ss_gie, 0x0001);
    
    /// Poll until controller reports ready
    do
    {
        get_reg(baseaddr + mipi_tx_ss_cfg, &ready) ;
    }
    while(ready & 0x0004U == 0U);

    /// Enable core operation
    set_reg(baseaddr + mipi_tx_ss_cfg, 0x0001);
    /// Start D-PHY transmission
    set_reg(baseaddr + d_phy_offset, 0x2);
}


/// Write a 32-bit value to a memory-mapped register
static void set_reg(uint32_t addr, uint32_t val)
{
    mem_map mm;
	memmap_init(&mm, addr);
	memmap_write(mm, addr, val);
	memmap_close(mm);
}

/// Read a 32-bit value from a memory-mapped register
static void get_reg(uint32_t addr, uint32_t *val)
{
    mem_map mm;
	memmap_init(&mm, addr);
	memmap_read(mm, addr, val);
	memmap_close(mm);
}