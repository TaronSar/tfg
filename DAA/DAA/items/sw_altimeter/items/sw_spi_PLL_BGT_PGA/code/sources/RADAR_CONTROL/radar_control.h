/* Enable C linkage if header is included in C++ files */
#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */
/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */
#include "../RF_DEV/RF_control.h"


/*
==============================================================================
   2. DATA
==============================================================================
 */

typedef void* Radar_Handle_t;


#define FW_MODULATION_TYPE      1U



/**
 * \brief Defines supported modulation types. Use type Modulation_Type_t for this enum.
 */
typedef enum
{
	MODULATION_DOPPLER	= 0U,  	/**< Doppler Modulation for speed calculation */
	MODULATION_FMCW		= 1U	/**< FMCW Modulation for range calculation*/
} Modulation_Type_t;


/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */