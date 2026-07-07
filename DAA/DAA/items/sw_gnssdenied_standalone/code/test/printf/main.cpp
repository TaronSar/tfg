#include <Printf.h>
#include <Clock.h>
#include <CortexA53/Cache.h>


int main()
{
    Zusp::Dcache::disable();
    
    /// Initialize UART - printf
    Zusp::UART uart(UART_0_baseaddr, 115200U);
    
    /// Wait for device initialization
    while (!uart.check_init())
    {
        ;
    }
    
    for (Uint16 i = 'A'; i <= 'Z'; i++)
    {
        uart.send_byte((Uint8)(i));
    }
    uart.send_byte((Uint8)('\n'));

    Zusp::Printf::printf("Hola mundo\n");

    int8  signed_8 = 15;
    Zusp::Printf::printf("signed_8: %d\n", signed_8);
    int16 signed_16 = 400;
    Zusp::Printf::printf("signed_16: %d\n", signed_16);
    int32 signed_32 = 655351;
    Zusp::Printf::printf("signed_32: %ld\n", signed_32);
    int64 signed_64 = 5454456546;
    Zusp::Printf::printf("signed_64: %lld\n", signed_64);

    Uint8  unsigned_8 = 12U;
    Zusp::Printf::printf("unsigned_8: %u\n", unsigned_8);
    Uint16 unsigned_16 = 333U;
    Zusp::Printf::printf("unsigned_16: %u\n", unsigned_16);
    Uint32 unsigned_32 = 0xFFFFF1;
    Zusp::Printf::printf("unsigned_32: %lu\n", unsigned_32);
    Uint64 unsigned_64 = 0xFFFFFFF1;
    Zusp::Printf::printf("unsigned_64: %llu\n", unsigned_64);
    Zusp::Printf::printf("unsigned_64: 0x%lx\n", unsigned_64);
    Zusp::Printf::printf("unsigned_64: 0x%x\n", &unsigned_64);

    Real real = 1.1f;
    Zusp::Printf::printf("real: %.3f\n", real);
    Real64 real_64 = 2.2F;
    Zusp::Printf::printf("real_64: %.3lf\n", real_64);

    Zusp::Printf::printf("%s %s %s %s.\n", "This", "is", "a", "string");

    return 0;
}
