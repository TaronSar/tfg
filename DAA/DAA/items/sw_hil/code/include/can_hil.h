
#ifndef CAN_HIL_H
#define CAN_HIL_H

#include <can_zusp.h>

class Can_hil : public Can{

public:
    Can_hil(const std::string& device, int bitrate);

    void ReadPose(double& latitude, double& longitude, double& altitude, float& roll, float& pitch, float& yaw, float& vx, float& vy, float& vz, bool& fix, bool& execution);
    void WritePose(double latitude, double longitude, double altitude, float roll, float pitch, float yaw, float timestamp, int shs, bool fix, bool execution);    

private:
    static const int can_frame_size = 50;

};

#endif