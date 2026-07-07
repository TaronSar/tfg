/**
 * @file u_dma_buf.c
 * @brief Library for U-DMA-BUF
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */


#include <sys/mman.h>
#include "u_dma_buf.h"

uint8_t u_dma_buf_setup(u_dma_buf* buffer, uint8_t id, uint32_t size)
{
	void* vAddr;
	char str[256];
    char read_buf[1024];
	int fd;
    uint64_t phys_addr;

	buffer->id = id;
	buffer->size = size;

   	snprintf(str, sizeof(str), "insmod %s udmabuf%d=%d", MODULE_PATH, buffer->id, buffer->size);

    
    if (access("/sys/class/u-dma-buf", F_OK) != -1) {
        printf("u-dma-buf is loaded yet.\n");
    }
	else{
		int status = system(str);
    	if (status == 0) {
    	    print("u-dma-buf module initialized.\n");
    	} else {
    	    print("u-dma-buf module not initialized.\n");
    	}
	}

   	snprintf(str, sizeof(str), "/sys/class/u-dma-buf/udmabuf%d/phys_addr", buffer->id);

    if ((fd  = open(str, O_RDONLY)) != -1) {
        (void)read(fd, read_buf, 1024);
        sscanf(read_buf, "%llx", &phys_addr);
        close(fd);
		print("U-DMA-BUF PYHSICAL ADDR: 0x%016llX\n", phys_addr);
		if((phys_addr >> 32U) != 0U)
		{
			print("u-dma-buf pyhsical address has more than 32 bits!!!\n");
		} 
    }
	else
	{
        print("u-dma-buf pyhsical address can't be read.\n");
	}

	buffer->phys_addr = phys_addr;


	if((size) > buffer->size)
	{
		print("Virtual space too large. Bytes tried to allocate: %d. Max bytes to allocate: %d\n", size, buffer->size);
		return 1;
	}

   	snprintf(str, sizeof(str), "/dev/udmabuf%d", buffer->id);
   	if ((fd  = open(str, O_RDWR | O_SYNC)) == -1) return NULL;
	vAddr = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
	if (vAddr == (void *) -1) return 1;	
	close(fd);

	buffer->virt_addr = vAddr;


    return 0;


}

uint64_t u_dma_buf_get_physical_addr(u_dma_buf buffer, uint32_t offset)
{
	return (buffer.phys_addr+(uint64_t)offset);
}

uint32_t u_dma_buf_get_size(u_dma_buf buffer)
{
	return (buffer.size);
}

void* u_dma_buf_get_virtual_space(u_dma_buf buffer, uint32_t offset, uint32_t size)
{
	
	if(offset + size > buffer.size)
	{
		print(" Virtual space too large. Bytes tried to allocate: %d at 0x%08X. Max bytes to allocate: %d\n", size, offset, buffer.size);
		return NULL;
	}

	print(" Virtual space required: Size: %d bytes vAddr base: 0x%016X, offset: 0x%08X\n", size, buffer.virt_addr, offset);
	//print("Virtual space required: Size: %d bytes vAddr base: 0x%016X, offset: 0x%08X\n", size, (&buf), offset);
	return ((void*)(buffer.virt_addr + offset));
}

// void set_dma_buff_path(const char* dma_buff)
// {
// 	strcmp(DMA_MODULE_PATH, dma_buff);
// }