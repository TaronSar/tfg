#include <Hex_dump.h>
#include <SD_driver.h>
#include <xil_cache.h>
#include <xparameters.h>

#include <cstdio>

namespace zusp
{
    void SD_driver::MBR::print()
    {
        for (int i = 0; i < 4; ++i)
        {
            const SD_driver::MBR_part_entry* p = &part[i];
            if (p->type == 0 && p->lba_first == 0 && p->sectors == 0) continue;
            Uint32 mib = p->sectors >> 11;
            printf("Part%d: type=0x%02X start=%lu len=%lu (~%lu MiB) boot=0x%02X\r\n",
                   i + 1,
                   p->type,
                   (unsigned long)p->lba_first,
                   (unsigned long)p->sectors,
                   (unsigned long)mib,
                   p->status);
        }
    }

    SD_driver& SD_driver::get_instance()
    {
        static SD_driver sd;
        return sd;
    }

    SD_driver::SD_driver()
    {
        int32 status;

        static const Uint32 SD_DEVICE_ID = XPAR_XSDPS_0_DEVICE_ID;

        XSdPs_Config* Cfg = XSdPs_LookupConfig(SD_DEVICE_ID);
        if (Cfg == NULL)
        {
            printf("XSdPs config not found\r\n");
        }

        status = XSdPs_CfgInitialize(&Sd, Cfg, Cfg->BaseAddress);
        if (status != 0)
        {
            printf("CfgInitialize failed\r\n");
        }

        status = XSdPs_CardInitialize(&Sd);
        if (status != 0)
        {
            printf("CardInitialize failed\r\n");
        }

        status = XSdPs_Change_BusWidth(&Sd);
        if (status != XST_SUCCESS)
        {
            // Puede que la tarjeta o la placa no soporte 4 bits, pero no es un error crítico.
            printf("Warning: Could not set 4-bit bus width.\n");
        }

        status = XSdPs_Change_BusSpeed(&Sd);
        if (status != XST_SUCCESS)
        {
            // Esto indica que la tarjeta no son compatibles con UHS-I.
            printf("Warning: UHS-I speed mode negotiation failed. Operating at lower speed.\n");
        }
    }

    SD_driver::Status SD_driver::partitions_talbe(MBR* mbr)
    {
        Uint8 sector_buffer[block_size_bytes];

        Status status = read(0, 1, sector_buffer);
        if (status != ok)
        {
            return status;
        }

        Hex_dump::print(sector_buffer, block_size_bytes);

        memcpy(mbr, sector_buffer, sizeof(MBR));

        if (mbr->signature != mbr_valid_signature)
        {
            return error_mbr_signature;
        }

        mbr->print();

        return ok;
    }

    SD_driver::Status SD_driver::read(const Uint32 sector_address, const Uint32 sector_count, Uint8* buffer)
    {
        Xil_DCacheInvalidateRange(reinterpret_cast<UINTPTR>(buffer), sector_count * block_size_bytes);

        int32 status = XSdPs_ReadPolled(&Sd, sector_address, sector_count, buffer);

        return (status == XST_SUCCESS) ? ok : error_read;
    }

    SD_driver::Status SD_driver::write(const Uint32 sector_address, const Uint32 sector_count, const Uint8* buffer)
    {
        Xil_DCacheFlushRange(reinterpret_cast<UINTPTR>(buffer), sector_count * block_size_bytes);

        int32 status = XSdPs_WritePolled(&Sd, sector_address, sector_count, buffer);

        return (status == XST_SUCCESS) ? ok : error_write;
    }
}