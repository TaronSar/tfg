#include <mipi_tx_ss.h>

extern "C" {
    #include <memmap.h>
}

static void set_reg(uint32_t addr, uint32_t val);
static void get_reg(uint32_t addr, uint32_t *val);


Mipi_tx_ss::Mipi_tx_ss(uint32_t baseaddr){
    
    uint32_t ready;

    // Disable interrupts
    set_reg(baseaddr + mipi_tx_ss_gie, 0x0000);
    // Clean triggered interrupts
    set_reg(baseaddr + mipi_tx_ss_ist, 0x003F);
    // Soft reset
    set_reg(baseaddr + mipi_tx_ss_cfg, 0x0002);

    // Disable and reset d_phy
    set_reg(baseaddr + d_phy_offset, 0x0);
    set_reg(baseaddr + d_phy_offset, 0x1);
    
    
    // Enable line start/end generation
    set_reg(baseaddr + mipi_tx_ss_prt, 0x8000);

    // Enable interrupts
    set_reg(baseaddr + mipi_tx_ss_gie, 0x0001);
    
    //Wait for controller ready 
    do{
        get_reg(baseaddr + mipi_tx_ss_cfg, &ready) ;
    }
    while(ready & 0x0004U == 0U);

    // Enable clore
    set_reg(baseaddr + mipi_tx_ss_cfg, 0x0001);
    // Run D-Phy
    set_reg(baseaddr + d_phy_offset, 0x2);


}



static void set_reg(uint32_t addr, uint32_t val){
    mem_map mm;
	memmap_init(&mm, addr);
	
	memmap_write(mm, addr, val);

	memmap_close(mm);

}


static void get_reg(uint32_t addr, uint32_t *val){

    mem_map mm;
	memmap_init(&mm, addr);

	memmap_read(mm, addr, val);

	memmap_close(mm);

}