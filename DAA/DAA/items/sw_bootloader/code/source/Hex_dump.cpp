#include <Hex_dump.h>

#include <cstdio>

namespace zusp
{
    static inline void put_hex8(Uint8 b)
    {
        static const char hex[] = "0123456789ABCDEF";
        printf("%c%c", hex[(b >> 4) & 0xF], hex[b & 0xF]);
    }

    void Hex_dump::print(const Uint8* buf, Uint32 len)
    {
        for (Uint32 i = 0; i < len; i += 16)
        {
            printf("%08X  ", (Uint32)i);  // offset
            // bytes en hex
            for (Uint32 j = 0; j < 16; ++j)
            {
                if (i + j < len)
                {
                    put_hex8(buf[i + j]);
                    printf(" ");
                }
                else
                    printf("   ");
            }
            printf(" ");
            // ASCII
            for (Uint32 j = 0; j < 16 && (i + j) < len; ++j)
            {
                Uint8 c = buf[i + j];
                printf("%c", (c >= 32 && c <= 126) ? c : '.');
            }
            printf("\r\n");
        }
    }
}