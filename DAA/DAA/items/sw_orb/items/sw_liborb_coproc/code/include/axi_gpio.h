/**
 * @file axi_gpio.h
 * @brief Library for AXI GPIO.
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */



#ifndef AXI_GPIO_H
#define AXI_GPIO_H

#include <stdint.h>

#include "dbg.h"
#include "memmap.h"

#define AXI_GPIO_DATA_OFFS      0x0000U

#define AXI_GPIO2_DATA_OFFS     0x0008U


typedef enum {
    AXI_GPIO,
    AXI_GPIO2
} axi_gpio_port;

typedef struct {
    uint32_t dev_base_addr;
    axi_gpio_port port;
} axi_gpio_conf;



uint8_t axi_gpio_set_pin(axi_gpio_conf config, uint8_t pin);
uint8_t axi_gpio_clear_pin(axi_gpio_conf config, uint8_t pin);

#endif // AXI_GPIO_H