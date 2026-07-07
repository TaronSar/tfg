#ifndef ZUSP_HW_IO_H_
#define ZUSP_HW_IO_H_

#include <Entypes.h> //from Vlibs
#include <CortexA53/Core_def.h> 

namespace Zusp
{
    class Hw_IO
    {
        public:
            static void hw_out8(Uintptr addr, Uint8 value); 
            static Uint8 hw_in8(Uintptr addr); 
            static void hw_out16(Uintptr addr, Uint16 value); 
            static Uint16 hw_in16(Uintptr addr); 
            static void hw_out32(Uintptr addr, Uint32 value); 
            static Uint32 hw_in32(Uintptr addr); 
            static void hw_out64(Uintptr addr, Uint64 value); 
            static Uint64 hw_in64(Uintptr addr); 

        private:
            Hw_IO(); ///< = delete
            Hw_IO(const Hw_IO& orig); ///< = delete
            ~Hw_IO(); ///< = delete
            Hw_IO& operator=(const Hw_IO& orig); ///< = delete

    };
}

#endif