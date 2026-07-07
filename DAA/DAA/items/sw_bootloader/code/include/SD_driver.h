#ifndef SD_H_
#define SD_H_

#include <Entypes.h>
#include <xsdps.h>

namespace zusp
{
    class SD_driver
    {
    public:
        static const Uint32 block_size_bytes = 512U;  ///< Standard block/sector size for SD cards in bytes

        // AV Rule 26
        // Compiler does not add padding to the structs
#pragma pack(push, 1)

        struct MBR_part_entry  // 16 bytes
        {
            Uint8 status;
            Uint8 chs_first[3];
            Uint8 type;
            Uint8 chs_last[3];
            Uint32 lba_first;
            Uint32 sectors;
        };

        /// Master Boot Record structure
        struct MBR
        {
            Uint8 boot_code[446];
            MBR_part_entry part[4];  // 4 * 16 = 64
            Uint16 signature;        // debe estar en offset 510

            void print();
        };

#pragma pack(pop)

        enum Status
        {
            ok,                  ///< Operation completed successfully.
            error_read,          ///< A read operation failed.
            error_write,         ///< A write operation failed.
            error_mbr_signature  ///< The MBR signature was invalid.
        };

        /// Gets the singleton instance of the SD_driver
        /// \return Reference to the SD_driver object
        static SD_driver& get_instance();

        /// Reads and validates the Master Boot Record from the SD card
        /// \param[out] mbr Pointer to an MBR struct to be filled with the data
        /// \return Status code indicating the result of the operation
        Status partitions_talbe(MBR* mbr);

        /// Reads one or more sectors from the SD card into a buffer
        /// \param[in] sector_address The starting Logical Block Address (LBA) to read to
        /// \param[in] sector_count The number of sectors to read
        /// \param[out] buffer A pointer to the destination buffer for the read data
        /// \return Status code indicating the result of the operation
        Status read(const Uint32 sector_address, const Uint32 sector_count, Uint8* buffer);

        /// Writes one or more sectors from a buffer to the SD card
        /// \param[in] sector_address The starting Logical Block Address (LBA) to write to
        /// \param[in] sector_count The number of sectors to write
        /// \param[in] buffer A pointer to the source buffer containing the data to write
        /// \return Status code indicating the result of the operation
        Status write(const Uint32 sector_address, const Uint32 sector_count, const Uint8* buffer);

    private:
        static const Uint32 mbr_valid_signature = 0xAA55U;  ///< boot signature at the end of a valid MBR

        SD_driver();

        XSdPs Sd;  ///< Xilinx Statndolone driver for the sd
    };
}

#endif