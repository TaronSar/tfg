extern "C"
{
#include <platform.h>
}

#include <Flash_partition.h>
#include <Multiboot.h>
#include <Resets.h>
#include <xtime_l.h>

#include <cstdio>

using namespace zusp;

void test_flash_sector(SD_driver::MBR* mbr)
{
    const SD_driver::MBR_part_entry partition = mbr->part[2U];
    Flash_partition fp(2U, partition);

    const Uint32 flash_size = SD_driver::block_size_bytes * Flash_partition::num_block;

    Uint8 buffer[flash_size];
    memset(buffer, 0XFF, flash_size);

    for (Uint16 i = 0; i < partition.sectors / Flash_partition::num_block; i++)
    {
        fp.flash_sector(buffer);
    }
}

void read_mbr()
{
    SD_driver sd = SD_driver::get_instance();
    SD_driver::MBR mbr;
    SD_driver::Status s = sd.partitions_talbe(&mbr);

    if (s != SD_driver::ok)
    {
        printf("ERRORS in SD\n\r");
    }
    else
    {
        XTime t_start;
        XTime t_end;

        XTime_GetTime(&t_start);
        test_flash_sector(&mbr);
        XTime_GetTime(&t_end);

        Uint64 clock_cycles = t_end - t_start;
        Uint64 microseconds = static_cast<Uint64>(clock_cycles / 30);

        xil_printf("test_flash_sector took %llu microseconds\n\r", microseconds);
    }
}

int main()
{
    init_platform();

    printf("Bootloader\n\r");

    read_mbr();

    /// Selector
    /// 0 = Bootloader, this
    /// 1 = Baremetal main 0001
    /// 2 = Baremetal main 0002
    /// 3 = Petalinux VBN
    Uint32 selector = 3U;

    Multiboot::select(selector);

    Resets::soft();

    while (true)
    {
    }

    return 0;
}
