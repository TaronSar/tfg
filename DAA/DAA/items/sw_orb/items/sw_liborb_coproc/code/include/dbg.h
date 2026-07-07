//----------------------------------------------------------------------//
//                         Debugging software                           //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//



#ifndef DBG_H
#define DBG_H

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

#ifdef VERBOSE
#define print(f_, ...) printf((f_), ##__VA_ARGS__)
#else
#define print(f_, ...) 
#endif


#endif // DBG_H