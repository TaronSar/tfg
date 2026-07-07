
#include "RF_control.h"
#include "sleep.h"
#ifdef SDT
#include "xinterrupt_wrap.h"

#endif



#define GPIO_DEVICE_ID		XPAR_XGPIOPS_0_DEVICE_ID
#define SPI_DEVICE_ID_0		XPAR_XSPIPS_0_DEVICE_ID

#define GPIO_INTERRUPT_ID	XPMC_GPIO_INT_ID

/*
==============================================================================
   2. DATA
==============================================================================
 */

static XSpiPs Spi0_pga;
static XSpiPs Spi0_bgt;
static XSpiPs Spi0_pll;

/* Declare BGT Object */
BGT_Object 		Bgt24_txrx;
/* Declare PGA Object */
PGA112_Object   Pga112_handle;
/* Declare PLL Object */
Lmx249x_Object_t  	Lmx249x_pll;


/*
==============================================================================
   3. LOCAL FUNCTION PROTOTYPES
==============================================================================
 */

int RF_init(void);

void RF_components_power_up(void);

void RF_components_power_down(void);

int PS_driver_init(void);

int PS_RF_init(){
	
	int Status;
	init_platform();

	Status = PS_driver_init();
	if (Status != XST_SUCCESS) {
		xil_printf("Failed. PS Drivers INIT.");
		return -1;
	}

	Status = RF_init();
	if (Status != XST_SUCCESS) {
		xil_printf("Failed. RF Components INIT.");
	}
	
	RF_components_power_up();

	cleanup_platform();
	return 0;
}


int PS_driver_init(void){

	int Status;

	static XGpioPs Gpio0;
	Status = GPIOPS_0_init(&Gpio0);
	if (Status != XST_SUCCESS) {
		xil_printf("GPIO Initialization Failed\r\n");
		return XST_FAILURE;
	}

	Status = IOs_Init(&Gpio0);
	if (Status != XST_SUCCESS) {
		xil_printf("IO Initialization Failed\r\n");
		return XST_FAILURE;
	}

	Status = Init_SPI(&Spi0_pga, SPI_DEVICE_ID_0, PGA_DEVICE);
	Status = Init_SPI(&Spi0_bgt, SPI_DEVICE_ID_0, BGT_DEVICE);
	Status = Init_SPI(&Spi0_pll, SPI_DEVICE_ID_0, LMX_DEVICE);


	if (Status != XST_SUCCESS) {
		xil_printf("SPI Initialization Failed\r\n");
		return XST_FAILURE;
	}
	return Status;
}

int RF_init(void){

	int Status;

	bgt_ldo_enable();
	// delay function

	pga_ldo_enable();
	// delay function

	/* Power-up BGT */
	bgt_power_up();
	// delay function

	/* Enable PLL power supply */
    pll_power_up();

	/* Initialize BGT */
	bgt_init(&Bgt24_txrx, LNA_GAIN_ENABLE, BGT_TX_POWER, &Spi0_bgt);
    bgt_lowest_power_with_q2_disable(&Bgt24_txrx); /* To avoid out of band spurs */
	
	/* Initialize PLL */
    Status = pll_init(&Lmx249x_pll, &Spi0_pll);
	//delay
	
	Status = pll_update_configuration(&Lmx249x_pll, FMCW_MODULATION);
	//delay

	/* Initialize PGA */
	Status = pga112_init(&Pga112_handle, PGA_GAIN, &Spi0_pga);
	//delay

	  /* Check if duty cycle is enabled */
  	if(bsp_duty_cycle_enable == ENABLED)
  	{
    	RF_components_power_down();
 	}
  	else	/* duty cycle disabled */
  	{
    	bgt_start_tx(&Bgt24_txrx);
  	}

	return (Status);
}


void RF_components_power_up(void)
{
  /* Power-up BGT */
  bgt_power_up();

  bgt_lowest_power_with_q2_disable(&Bgt24_txrx);

  /* Enable BGT TX Power amplifier */
  bgt_start_tx(&Bgt24_txrx);
}

void RF_components_power_down(void)
{
  /* To avoid out of band spurs */
  bgt_lowest_power_with_q2_disable(&Bgt24_txrx);

  /* Power-down BGT */
  bgt_power_down();
}

static void get_raw_data(void)
{
	/* BGT and PLL Power-up */
	if(bsp_duty_cycle_enable == ENABLED)
	{
	   RF_components_power_up();
	  }
}