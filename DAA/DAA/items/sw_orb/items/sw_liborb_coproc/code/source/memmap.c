//----------------------------------------------------------------------//
//                         MMAP                                         //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//
//References -- https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842018/Linux+User+Mode+Pseudo+Driver
// Access to a peripheral by MMAP required to be disabled at device tree -- https://support.xilinx.com/s/question/0D52E00006hpkBySAI/bus-error-is-occured-when-get-data-from-mmap-address?language=en_US

#include "memmap.h"


uint8_t memmap_init(mem_map* mm, uint32_t memAddr){

    int memfd;
    memAddr &= (uint32_t)~(MAP_SIZE-1U);
    
    mmap_print("Memory mapped (0x%08X) ...", memAddr);
    memfd = open("/dev/mem",O_RDWR | O_CREAT | O_TRUNC | O_SYNC, 0x0777);
        if (memfd == -1) {
        perror("Can't open /dev/mem.\n");
        exit(0);
    }
    mmap_print("/dev/mem opened.\n");

    mm->mapped_base = mmap(NULL, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, memfd, memAddr);
        if (mm->mapped_base == (void *) -1) {
        print("Can't map the memory to user space. Memory area addr: 0x%08X\n", memAddr);
        exit(0);
    }
    mmap_print(" at address %p.\n",  mapped_base);
    mm->memoryBase = memAddr;

    close(memfd);
    return 0;
}


uint8_t memmap_read(mem_map mm, uint32_t addr_reg, uint32_t *reg) {
    mmap_print("MMAP Read: 0x%08X ...\n",addr_reg);
	*reg = *((volatile unsigned int*) (mm.mapped_base+(addr_reg-mm.memoryBase)));
    mmap_print("\r0x%08X OK\n ", *reg);
    return 0;

}

uint8_t memmap_write(mem_map mm, uint32_t addr_reg, uint32_t reg) {

    mmap_print("MMAP Write: 0x%08X ...",addr_reg);
	*((volatile unsigned int *) (mm.mapped_base+(addr_reg-mm.memoryBase))) = reg;
    mmap_print(" OK\n ");
    return 0;
}

uint8_t memmap_write_byte(mem_map mm,uint32_t addr_reg, char reg) {

    mmap_print("MMAP Write: 0x%08X ...",addr_reg);
	*((volatile char *) (mm.mapped_base+(addr_reg-mm.memoryBase))) = reg;
    mmap_print(" OK\n ");
    return 0;
}

uint8_t memmap_close(mem_map mm){

    if (munmap(mm.mapped_base, MAP_SIZE) == -1) {
        mmap_print("Can't unmap memory from user space.\n");
        return 1;
    }
    mmap_print("CLOSED Memory mapped (0x%08X) at address %p.\n\n", memoryBase, mapped_base);
    return 0;
}


