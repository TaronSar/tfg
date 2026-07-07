#ifndef HEX_DUMP_H_
#define HEX_DUMP_H_

#include <Entypes.h>

namespace zusp
{
    class Hex_dump
    {
    public:
        static void print(const Uint8* buf, Uint32 len);
    };
}

#endif