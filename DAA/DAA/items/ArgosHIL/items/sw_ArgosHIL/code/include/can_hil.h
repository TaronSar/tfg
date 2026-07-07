#ifndef CAN_HIL_H
#define CAN_HIL_H

#include <CAN_plnx.h>

#include <cstdint>
#include <string>

/// CAN bus HIL interface.
/// Handles pose data serialization and transmission over CAN bus
/// between the HIL system and Veronte autopilot.
class Can_hil
{
public:
    /// CAN HIL constructor.
    /// Initializes the CAN driver with specified device and bitrate.
    /// \param[in] device CAN interface name (e.g. "can0").
    /// \param[in] bitrate CAN bus speed in bps.
    Can_hil(const std::string& device, int bitrate);

    /// Read a pose message from CAN bus.
    /// Blocks until a complete pose frame is received.
    /// \param[out] latitude Latitude in degrees.
    /// \param[out] longitude Longitude in degrees.
    /// \param[out] altitude Altitude in meters.
    /// \param[out] roll Roll angle in radians.
    /// \param[out] pitch Pitch angle in radians.
    /// \param[out] yaw Yaw angle in radians.
    /// \param[out] vx Velocity X component.
    /// \param[out] vy Velocity Y component.
    /// \param[out] vz Velocity Z component.
    /// \param[out] fix GNSS fix status.
    /// \param[out] execution Execution flag from Veronte.
    void ReadPose(double& latitude, double& longitude, double& altitude,
                  float& roll, float& pitch, float& yaw,
                  float& vx, float& vy, float& vz,
                  bool& fix, bool& execution);

    /// Write a pose message to CAN bus.
    /// Serializes and splits the pose data into CAN frames.
    /// \param[in] latitude Latitude in degrees.
    /// \param[in] longitude Longitude in degrees.
    /// \param[in] altitude Altitude in meters.
    /// \param[in] roll Roll angle in radians.
    /// \param[in] pitch Pitch angle in radians.
    /// \param[in] yaw Yaw angle in radians.
    /// \param[in] timestamp Frame timestamp in seconds.
    /// \param[in] shs SHS parameter.
    /// \param[in] fix GNSS fix status.
    /// \param[in] execution Execution flag.
    void WritePose(double latitude, double longitude, double altitude,
                   float roll, float pitch, float yaw,
                   float timestamp, int shs,
                   bool fix, bool execution);

private:
    static const int can_frame_size = 50;          ///< Serialized pose frame size in bytes.
    static const Uint32 can_id_rd   = 0x515U;      ///< CAN ID for GPS -> Veronte (1301).
    static const Uint32 can_id_wr   = 0x516U;      ///< CAN ID for Veronte -> HIL (1302).

    CAN_plnx driver;  ///< CAN bus driver instance.
    Uint8    pkg_cnt; ///< Packet counter for CAN frame sequencing.
};

#endif
