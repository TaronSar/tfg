#ifndef FLASH_SECTOR_H_
#define FLASH_SECTOR_H_

#include <SD_driver.h>
#include <Stlvector.h>

#include <cstdio>

namespace zusp
{
    class Flash_partition
    {
    public:
        static const Uint32 num_block = 2048U;  ///< Defines the number of sectors to handle in a single logical block.
                                                ///< (2048 sectors * 512 bytes/sector = 1 MB)

        struct Flash_error_t
        {
            Uint8 id;                  ///< The identifier of the Flash_partition instance where the error occurred.
            SD_driver::Status status;  ///< The specific error code returned by the SD driver.
            Uint32 sector;             ///< The sector address (LBA) that failed.
        };

        /// Constructor to flash an entire partition
        /// \param id0 A unique identifier for this flash operation instance.
        /// \param partition0 The MBR entry describing the target partition.
        Flash_partition(const Uint8 id0, const SD_driver::MBR_part_entry& partition0);

        /// Constructor to flash a specific number of bytes into a partition.
        /// \param id0 A unique identifier for this flash operation instance.
        /// \param partition0 The MBR entry describing the target partition.
        /// \param bytes The total number of bytes to write. The actual number of sectors will be calculated from this
        /// value.
        Flash_partition(const Uint8 id0, const SD_driver::MBR_part_entry& partition0, const Uint64 bytes);

        /// Writes the next sequential sector to the partition.
        /// This method writes the provided buffer to the next available sector within the
        /// partition's boundaries and increments the internal progress counter.
        /// \param buffer Pointer to the source data buffer. Must be 512 bytes in size.
        void flash_sector(const Uint8* buffer);

        /// Verifies the integrity of the data written to the partition.
        /// This method should be called after all sectors have been flashed.
        /// It can implement checks like CRC or checksum validation by reading the data back.
        /// TODO: The specific integrity check logic needs to be implemented).
        /// @return Returns true if the integrity check passes, false otherwise.
        bool check_partition();

    private:
        const Uint8 id;                             ///< Id of the partition
        const SD_driver::MBR_part_entry partition;  ///< The target partition

        Uint32 sectors_flashed;              ///< A counter for the number of sectors successfully written so far.
        const Uint32 sectors_to_be_flashed;  ///< The total number of sectors that are scheduled to be written in this
                                             ///< session.

        Base::Stlvector<Flash_error_t> errors;  ///< A list to store any errors that occur during the write operations.
    };
}

#endif