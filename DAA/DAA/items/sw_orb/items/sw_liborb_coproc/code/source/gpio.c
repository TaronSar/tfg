//----------------------------------------------------------------------//
//                        GPIO Linux Driver                             //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include <stdio.h>
#include <inttypes.h>
#include <fcntl.h>
#include <dirent.h>

#include "gpio.h"


/**
 * Function to find the ZynqMP base gpiochip number by scanning /sys/class/gpio/.
 * It dynamically detects the base by searching for the "zynqmp-gpio" label.
 *
 * @param num_gpio A pointer to a uint32_t where the detected base number will be stored.
 * @return 0 on success, -1 on failure (e.g., if the directory cannot be opened).
 */
int read_gpio_xtrig(uint32_t* num_gpio)
{
    DIR *dir;
    struct dirent *entry;
    const uint16_t max_path_len = 256;
    const uint16_t max_label_len = 64;
    const uint16_t max_number_gpios = 77;
    const uint16_t emio_number_xtrig = 2;
    char path[max_path_len];
    char label_content[max_label_len];
    FILE *label_fp;
    uint16_t base_addr = 0;

    // 1. Open the /sys/class/gpio/ directory
    dir = opendir("/sys/class/gpio/");
    if (dir == NULL)
    {
        perror("Error opening directory /sys/class/gpio/\n");
        return -1;
    }

    // Iterate all directory entries
    while ((entry = readdir(dir)) != NULL) {
        // Ensure the entry is named with the "gpiochip" prefix
        if (strncmp(entry->d_name, "gpiochip", 8) == 0) // && entry->d_type == DT_DIR)
        {
            // Construir la ruta completa al archivo "label"
            snprintf(path, max_path_len, "%s%s/%s", "/sys/class/gpio/", entry->d_name, "label");

            // 3. Open the "label" file to read its content
            label_fp = fopen(path, "r");
            if (label_fp != NULL)
            {
                // 4. Read the content of the label (it should be short)
                if (fgets(label_content, max_label_len, label_fp) != NULL)
                {
                    // 5. Search for the "zynqmp-gpio" label
                    if (strstr(label_content, "zynqmp_gpio") != NULL)
                    {
                        // 6. Found! Extract the base number.
                        // entry->d_name is, for example, "gpiochip420"
                        // Remove the "gpiochip" prefix and convert the rest to an integer.
                        base_addr = atoi(entry->d_name + strlen("gpiochip"));
        
                        // Close the label file and break the loop
                        fclose(label_fp);
                        break;
                    }
                }
                // 7. If it doesn't match, close the label and continue with the next chip
                fclose(label_fp);
            }
        }
    }

    *num_gpio = base_addr + max_number_gpios + emio_number_xtrig;

    printf("[---] Num gpio read: %d\n", *num_gpio);

    // 8. Close the main directory
    closedir(dir);

    return 0;
}


uint8_t gpio_init(uint32_t num_gpio, char sel_dir){

	char buf[256];
	FILE * gpio_fd;


    snprintf(buf, sizeof(buf), "/sys/class/gpio/export");
    gpio_fd = fopen(buf, "w");
    if (gpio_fd == NULL) {
		  print("Error to init gpio\n");
		  return 1;
    }
    fprintf(gpio_fd, "%d", num_gpio);
    fclose(gpio_fd);
		
	// set a direction
    snprintf(buf, sizeof(buf), "/sys/class/gpio/gpio%d/direction", num_gpio);
    gpio_fd = fopen(buf, "w");
    if (gpio_fd == NULL) {
		  print("Error to set direction gpio\n");
		  return 1;
    }
	if(sel_dir == OUTPUT){
		fprintf(gpio_fd, "out");
	}
	else{
		fprintf(gpio_fd, "in");
	}
    fclose(gpio_fd);
	return 0;
}


uint8_t gpio_set(uint32_t num_gpio, gpio_val val)
{


	char buf[256];
	FILE * gpio_fd;

    snprintf(buf, sizeof(buf), "/sys/class/gpio/gpio%d/value", num_gpio);
    gpio_fd = fopen(buf, "w");
    if (gpio_fd == NULL) {
        print("Error to set gpio.\n");
		    return 1;
    }
    fprintf(gpio_fd, "%d", val);
    fclose(gpio_fd);

	return 0;

};

uint8_t gpio_close(uint32_t num_gpio)
{


	char buf[256];
	FILE * gpio_fd;

    snprintf(buf, sizeof(buf), "/sys/class/gpio/unexport");
    gpio_fd = fopen(buf, "w");
    if (gpio_fd == NULL) {
		  print("Error to close gpio\n");
		  return 1;
    }
    fprintf(gpio_fd, "%d", num_gpio);
    fclose(gpio_fd);

	return 0;

};
