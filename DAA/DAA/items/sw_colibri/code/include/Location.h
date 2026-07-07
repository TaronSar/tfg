#ifndef __LOCATION_WRAPPER_
#define __LOCATION_WRAPPER_

#include <Eigen/Eigen>

namespace Vbn
{
    class Location_wrapper
    {
        public:
            Location_wrapper(
                const std::string& camera_settings,
                const std::string& aruco_settings,
                const uint8_t& dictionary_size,
                const float& system_rotation
            );
            void undistort(void* image);
            bool locate(void* image, Eigen::Matrix3f& R, Eigen::Vector3f& t);
            ~Location_wrapper() = default;
        private:
            class Impl;
            Impl* pImpl;
    };

}

#endif