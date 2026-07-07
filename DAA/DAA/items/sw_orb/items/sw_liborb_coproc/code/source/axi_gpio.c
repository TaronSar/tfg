/**
 * @file axi_gpio.c
 * @brief Library for AXI GPIO.
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */

#include <stdio.h>
#include <inttypes.h>
#include <fcntl.h>

#include "axi_gpio.h"

static uint32_t data_register;

static void set_reg(uint32_t addr, uint32_t val){
    mem_map mm;
	memmap_init(&mm, addr);
	
	memmap_write(mm, addr, val);

	memmap_close(mm);

}

uint8_t axi_gpio_set_pin(axi_gpio_conf config, uint8_t pin)
{
    uint32_t data_reg_addr;

    if(pin > 32 || pin < 0) return 1;

    if(config.port == AXI_GPIO) data_reg_addr = config.dev_base_addr + AXI_GPIO_DATA_OFFS;
    else data_reg_addr = config.dev_base_addr + AXI_GPIO2_DATA_OFFS;


    data_register |= ((uint32_t)1U << pin);
    set_reg(data_reg_addr, data_register);

	return 0;

};

uint8_t axi_gpio_clear_pin(axi_gpio_conf config, uint8_t pin)
{
    uint32_t data_reg_addr;

    if(pin > 32 || pin < 0) return 1;

    if(config.port == AXI_GPIO) data_reg_addr = config.dev_base_addr + AXI_GPIO_DATA_OFFS;
    else data_reg_addr = config.dev_base_addr + AXI_GPIO2_DATA_OFFS;


    data_register &= ~((uint32_t)1U << pin);
    set_reg(data_reg_addr, data_register);

	return 0;

};