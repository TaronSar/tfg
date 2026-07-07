//----------------------------------------------------------------------//
//                         BRAM                                         //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: March 2025                                                     //
//----------------------------------------------------------------------//


#include "bram.h"


uint8_t bram_init(mem_map* mm, uint32_t memAddr, uint32_t size){

    int memfd;
    
    mmap_print("Memory mapped (0x%08X) ...", memAddr);
    memfd = open("/dev/mem",O_RDWR | O_CREAT | O_TRUNC | O_SYNC, 0x0777);
        if (memfd == -1) {
        perror("Can't open /dev/mem.\n");
        exit(0);
    }
    mmap_print("/dev/mem opened.\n");

    mm->mapped_base = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, memfd, memAddr);
        if (mm->mapped_base == (void *) -1) {
        print("Can't map the memory to user space. Memory area addr: 0x%08X\n", memAddr);
        exit(0);
    }
    mmap_print(" at address %p.\n",  mapped_base);
    mm->memoryBase = memAddr;

    close(memfd);
    return 0;
}


void* bram_get_ptr(mem_map mm, uint32_t offset) {
	return ((void *) (mm.mapped_base+(offset))) ;
}


uint8_t bram_close(mem_map mm){

    if (munmap(mm.mapped_base, MAP_SIZE) == -1) {
        mmap_print("Can't unmap memory from user space.\n");
        return 1;
    }
    mmap_print("CLOSED Memory mapped (0x%08X) at address %p.\n\n", memoryBase, mapped_base);
    return 0;
}


