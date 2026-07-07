#include <Flash_partition.h>

namespace zusp
{
    Flash_partition::Flash_partition(const Uint8 id0, const SD_driver::MBR_part_entry& partition0) :
        id(id0),
        partition(partition0),
        sectors_flashed(0U),
        sectors_to_be_flashed((partition.sectors + num_block - 1) / num_block),
        errors(1, Base::Memmgr::external)
    {
        errors.zeros();
        printf("Particion %u. Se flasean %u sectores en bloques de %u * %u bytes\n\r",
               id + 1U,
               sectors_to_be_flashed,
               SD_driver::block_size_bytes,
               num_block);
    }

    Flash_partition::Flash_partition(const Uint8 id0,
                                     const SD_driver::MBR_part_entry& partition0,
                                     const Uint64 bytes) :
        id(id0),
        partition(partition0),
        sectors_flashed(0U),
        sectors_to_be_flashed((partition.sectors + num_block - 1) / num_block),
        errors(1, Base::Memmgr::external)
    {
    }

    void Flash_partition::flash_sector(const Uint8* buffer)
    {
        static SD_driver& sd = SD_driver::get_instance();

        // Comprobar si es el último bloque y ajustar el tamaño si es parcial
        Uint32 sectors_left     = partition.sectors - (sectors_flashed * num_block);
        Uint32 sectors_to_write = (sectors_left < num_block) ? sectors_left : num_block;

        // base + (operación_actual * tamaño_del_bloque)
        Uint32 target_lba = partition.lba_first + (sectors_flashed * num_block);

        SD_driver::Status status = sd.write(target_lba, sectors_to_write, buffer);

        if (status != SD_driver::ok)
        {
            errors.push_back({id, status, sectors_flashed});
            printf("ERROR Flasing in %u / %u\n\r", sectors_flashed, sectors_to_be_flashed);
        }

        sectors_flashed++;
    }

    bool Flash_partition::check_partition()
    {
        bool res = false;
        // TODO: Add a checksum or a CRC to check that the partition is not corrupted
        if (sectors_flashed == sectors_to_be_flashed)
        {
            res = true;
        }

        if (res == false)
        {
            printf("CRITICAL ERROR: The partition: %d, has a integrity error\n\r", id);
        }

        return res;
    }
}