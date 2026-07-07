//
// Hardware Input/Output specific implementation (Xillinx Zynq Ultrascale+ hardware).
// ZUSP namespace (Baremetal)
// 
// Copyright (c) 2024 - Embention S.A. JSF++ Software
//

#include <Hw_IO.h>

namespace Zusp
{
    Uint8 Hw_IO::hw_in8(Uintptr addr)
    {
        return *(volatile Uint8 *) addr;
    }

    Uint16 Hw_IO::hw_in16(Uintptr addr)
    {
        return *(volatile Uint16 *) addr;
    }

    Uint32 Hw_IO::hw_in32(Uintptr addr)
    {
        return *(volatile Uint32 *) addr;
    }

    Uint64 Hw_IO::hw_in64(Uintptr addr)
    {
        return *(volatile Uint64 *) addr;
    }


    void Hw_IO::hw_out8(Uintptr addr, Uint8 value)
    {
	    volatile Uint8 *local_addr = (volatile Uint8 *)addr;
	    *local_addr = value;
    }

    void Hw_IO::hw_out16(Uintptr addr, Uint16 value)
    {
	    volatile Uint16 *local_addr = (volatile Uint16 *)addr;
	    *local_addr = value;
    }

    void Hw_IO::hw_out32(Uintptr addr, Uint32 value)
    {
	    volatile Uint32 *local_addr = (volatile Uint32 *)addr;
	    *local_addr = value;
    }

    void Hw_IO::hw_out64(Uintptr addr, Uint64 value)
    {
	    volatile Uint64 *local_addr = (volatile Uint64 *)addr;
	    *local_addr = value;
    }

}