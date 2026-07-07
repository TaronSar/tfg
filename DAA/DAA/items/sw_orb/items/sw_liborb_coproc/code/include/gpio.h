//----------------------------------------------------------------------//
//                        GPIO Linux Driver                             //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#ifndef GPIO_H
#define GPIO_H

#include <stdint.h>

#include "dbg.h"

typedef enum {
    INPUT = 0,
    OUTPUT = 1
} gpio_dir;

typedef enum {
    LOW = 0,
    HIGH = 1
} gpio_val;

int read_gpio_xtrig(uint32_t* num_gpio);
uint8_t gpio_init(uint32_t num_gpio, char sel_dir);
uint8_t gpio_set(uint32_t num_gpio, gpio_val val);
uint8_t gpio_close(uint32_t num_gpio);


#endif // GPIO_H