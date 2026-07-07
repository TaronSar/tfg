#include <can_hil.h>

#include <cstring>
#include <iostream>
#include <unistd.h>


Can_hil::Can_hil(const std::string& device, int bitrate)
    : driver(device, static_cast<Uint32>(bitrate)),
      pkg_cnt(0U)
{
}


void Can_hil::ReadPose(double& latitude, double& longitude, double& altitude,
                       float& roll, float& pitch, float& yaw,
                       float& vx, float& vy, float& vz,
                       bool& fix, bool& execution)
{
    unsigned char response[can_frame_size];
    CAN_frame rx;
    int  resp_idx     = 0;
    bool start_frame  = false;
    bool end_frame    = false;

    /// Block until a complete frame is assembled from CAN packets
    do
    {
        if (!driver.read_frame(rx))
        {
            continue;
        }

        int header_size = 0;

        /// Detect start-of-frame marker (0x5A)
        if (!start_frame && rx.data[0] == 0x5A)
        {
            start_frame = true;
            header_size = 1;
        }

        /// Append payload bytes to response buffer
        if (start_frame)
        {
            int i = 0;
            for (; i < (rx.size - header_size); i++)
            {
                if ((resp_idx + i) < can_frame_size)
                {
                    response[resp_idx + i] = rx.data[i + header_size];
                }
            }
            resp_idx += i;
        }

        /// Check end-of-frame marker (0xAA) or overflow
        if (resp_idx >= (can_frame_size - 1) && response[can_frame_size - 1] == 0xAA)
        {
            end_frame = true;
            std::cout << "correct" << std::endl;
        }
        else if (resp_idx > (can_frame_size - 1))
        {
            resp_idx    = 0;
            start_frame = false;
            std::cout << "fail" << std::endl;
        }
    } while (!end_frame);

    /// Deserialize pose fields from raw buffer
    uint64_t latitude_64  = ((uint64_t*)response)[0];
    uint64_t longitude_64 = ((uint64_t*)response)[1];
    uint64_t altitude_64  = ((uint64_t*)response)[2];
    uint32_t roll_32      = ((uint32_t*)response)[6];
    uint32_t pitch_32     = ((uint32_t*)response)[7];
    uint32_t yaw_32       = ((uint32_t*)response)[8];
    uint32_t vx_32        = ((uint32_t*)response)[9];
    uint32_t vy_32        = ((uint32_t*)response)[10];
    uint32_t vz_32        = ((uint32_t*)response)[11];

    /// Extract status flags from penultimate byte
    execution = (bool)(response[can_frame_size - 2] & 0x02);
    fix       = (bool)(response[can_frame_size - 2] & 0x01);

    /// Reinterpret raw integers back to floating-point
    latitude  = *((double*)&latitude_64);
    longitude = *((double*)&longitude_64);
    altitude  = *((double*)&altitude_64);
    roll      = *((float*)&roll_32);
    pitch     = *((float*)&pitch_32);
    yaw       = *((float*)&yaw_32);
    vx        = *((float*)&vx_32);
    vy        = *((float*)&vy_32);
    vz        = *((float*)&vz_32);
}


void Can_hil::WritePose(double latitude, double longitude, double altitude,
                        float roll, float pitch, float yaw,
                        float timestamp, int shs,
                        bool fix, bool execution)
{
    unsigned char package[can_frame_size];
    std::memset(package, 0, sizeof(package));

    /// Serialize doubles via memcpy to avoid strict-aliasing issues
    uint64_t latitude_64;
    uint64_t longitude_64;
    uint64_t altitude_64;

    std::memcpy(&latitude_64,  &latitude,  sizeof(double));
    std::memcpy(&longitude_64, &longitude, sizeof(double));
    std::memcpy(&altitude_64,  &altitude,  sizeof(double));

    /// Build payload: [0xAA header][lat][lon][alt][rpy][ts][shs][flags][0x5A footer]
    package[1] = 0xAA;
    ((uint64_t*)(package + 2))[0] = latitude_64;
    ((uint64_t*)(package + 2))[1] = longitude_64;
    ((uint64_t*)(package + 2))[2] = altitude_64;
    std::memcpy(package + 26, &roll,      sizeof(float));
    std::memcpy(package + 30, &pitch,     sizeof(float));
    std::memcpy(package + 34, &yaw,       sizeof(float));
    std::memcpy(package + 38, &timestamp, sizeof(float));
    std::memcpy(package + 42, &shs,       sizeof(int));
    package[46] = (fix       ? 0x80 : 0x00);
    package[46] |= (execution ? 0x40 : 0x00);
    package[47] = 0x00;
    package[48] = 0x00;
    package[49] = 0x5A;

    /// Fragment into 7 CAN frames (7 payload bytes + 1 counter byte each)
    int pending_bytes = 49;
    for (int i = 0; i < 7; i++)
    {
        CAN_frame tx;
        tx.can_id = can_id_rd;
        tx.data[0] = pkg_cnt;
        std::memcpy(&tx.data[1], package + (i * 7), 7);
        tx.size = (pending_bytes >= 7) ? 8 : (pending_bytes + 1);

        (void)driver.write_frame(tx);

        pending_bytes -= 7;
        pkg_cnt++;
        usleep(10);
    }
}
