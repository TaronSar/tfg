#include <Printf.h>
#include <DMA.h>
#include <Hw_IO.h>
#include <CortexA53/Cache.h>

// Direcciones base y de destino de ejemplo
static const Uint64 base_addr_DMA_0 = 0x80000000U;
static const Uint64 base_addr_DMA_1 = 0x80010000U;
// static const Uint64 sz = 74U * 1024U * 1024U / 4U;
static const Uint64 sz = 64U;


void print_reg()
{
    Zusp::Printf::printf("Base addres DMA 0: 0x%x\n", Zusp::Hw_IO::hw_in32(base_addr_DMA_0));
    Zusp::Printf::printf("Base addres DMA 1: 0x%x\n", Zusp::Hw_IO::hw_in32(base_addr_DMA_1));

    Zusp::Printf::printf("Staus DMA 0: 0x%x\n", Zusp::Hw_IO::hw_in32(base_addr_DMA_0 + 0x4U));
    Zusp::Printf::printf("Staus DMA 1: 0x%x\n", Zusp::Hw_IO::hw_in32(base_addr_DMA_1 + 0x4U));
}

int main()
{
    /// Initialize UART0 - printf
    Zusp::UART::init(Zusp::UART_0, 115200U, UART_0_baseaddr);

    /// Wait for device initialization
    while (!Zusp::UART::get_UART(Zusp::UART_0)->check_init())
    {
        ;
    }

    Uint32 dest_buffer[sz];
    Uint32 source_buffer[sz];


    Zusp::Dcache::disable();

    // Inicializar buffers
    for (Uint64 i = 0U; i < sz; i++)
    {
        source_buffer[i] = i + 1; // Datos de ejemplo: 1, 2, 3...
        dest_buffer[i] = 0x0000;  // Destino inicializado a cero
    }

    Zusp::Printf::printf("Probando DMA con conexión s2mm a mm2s...\n");

    /// Configuración del DMA para escritura y lectura
    // Zusp::DMA dma_write(base_addr_DMA_1, reinterpret_cast<Uintptr>(dest_buffer), sz * 4U);
    // Zusp::DMA dma_read(base_addr_DMA_0, reinterpret_cast<Uintptr>(source_buffer), sz * 4U);
    Zusp::DMA dma_0(base_addr_DMA_0);
    Zusp::Printf::printf("dma_0\n");
    Zusp::DMA dma_1(base_addr_DMA_1);
    Zusp::Printf::printf("dma_1\n");
    dma_0.create(Zusp::write, reinterpret_cast<Uintptr>(dest_buffer), sz * 4U);
    Zusp::Printf::printf("dma_0.create\n");
    dma_1.create(Zusp::read, reinterpret_cast<Uintptr>(source_buffer), sz * 4U);
    Zusp::Printf::printf("dma_1.create\n");


    // Mostrar direcciones de memoria
    Zusp::Printf::printf("Dirección de dest_buffer: 0x%lx\n", reinterpret_cast<Uintptr>(dest_buffer));
    Zusp::Printf::printf("Dirección de source_buffer: 0x%lx\n", reinterpret_cast<Uintptr>(source_buffer));

    print_reg();

    // Iniciar ambos canales de DMA
    if (dma_1.read_channel->run_channel() != 0)
    {
        Zusp::Printf::printf("Error al ejecutar el DMA de lectura.\n");
        return 1;
    }

    if (dma_0.write_channel->run_channel() != 0)
    {
        Zusp::Printf::printf("Error al ejecutar el DMA de escritura.\n");
        return 1;
    }

    print_reg();

    // Esperar a que ambos DMA terminen
    if (dma_1.read_channel->wait_idle() != 0)
    {
        Zusp::Printf::printf("Error al esperar que el DMA de lectura termine.\n");
        return 1;
    }

    if (dma_0.write_channel->wait_idle() != 0)
    {
        Zusp::Printf::printf("Error al esperar que el DMA de escritura termine.\n");
        return 1;
    }

    // Verificar los datos transferidos
    bool success = true;
    for (Uint16 i = 0; i < sz; i++)
    {
        // Zusp::Printf::printf("dest_buffer %d: 0x%x\n", i, dest_buffer[i]);
        if (dest_buffer[i] != source_buffer[i])
        {
            Zusp::Printf::printf("Error: Diferencia en la posición %d: 0x%x != 0x%x\n", i, dest_buffer[i], source_buffer[i]);
            success = false;
            break;
        }
    }

    print_reg();


    if (success)
    {
        Zusp::Printf::printf("Prueba exitosa: Los datos coinciden.\n\n\n");
    }
    else
    {
        Zusp::Printf::printf("Prueba fallida: Los datos no coinciden.\n\n\n");
    }

    return success ? 0 : 1;
}
