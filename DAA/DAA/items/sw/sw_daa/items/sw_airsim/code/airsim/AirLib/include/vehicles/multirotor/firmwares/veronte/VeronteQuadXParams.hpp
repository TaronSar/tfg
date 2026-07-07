// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#ifndef msr_airlib_vehicles_VeronteQuadX_hpp
#define msr_airlib_vehicles_VeronteQuadX_hpp

#include "vehicles/multirotor/firmwares/veronte/VeronteApi.hpp"
#include "vehicles/multirotor/MultiRotorParams.hpp"
#include "common/AirSimSettings.hpp"
#include "common/Settings.hpp"
#include "sensors/SensorFactory.hpp"

namespace msr
{
namespace airlib
{

    class VeronteQuadXParams : public MultiRotorParams
    {
    public:
        VeronteQuadXParams(const AirSimSettings::VehicleSetting* vehicle_setting, std::shared_ptr<const SensorFactory> sensor_factory)
            : vehicle_setting_(vehicle_setting), sensor_factory_(sensor_factory)
        {
        }

        virtual ~VeronteQuadXParams() = default;

        virtual std::unique_ptr<MultirotorApiBase> createMultirotorApi() override
        {
            return std::unique_ptr<MultirotorApiBase>(new VeronteApi(this, vehicle_setting_));
        }

    protected:
        virtual void setupParams() override
        {
            auto& params = getParams();
            Settings vehicles_child;
            Settings vehicle_child;
            const Settings& settings = Settings::singleton();
            bool has_vehicle_settings = false;

            int rotor_count = 4;
            if (settings.getChild("Vehicles", vehicles_child) &&
                vehicles_child.getChild(vehicle_setting_->vehicle_name, vehicle_child)) {
                has_vehicle_settings = true;
                rotor_count = vehicle_child.getInt("RotorCount", rotor_count);
            }

            switch (rotor_count) {
            case 4:
                setupFrameGenericQuad(params);
                break;
            case 5:
                setupFrameGenericPenta(params);
                break;
            case 6:
                setupFrameGenericHex(params);
                break;
            case 8:
                setupFrameGenericOcto(params);
                break;
            default:
                if (rotor_count >= 4 && rotor_count <= 16) {
                    setupFrameGenericN(params, static_cast<uint>(rotor_count));
                }
                else {
                    throw std::invalid_argument("Unsupported RotorCount for Veronte. Supported values: 4..16");
                }
            }

            if (has_vehicle_settings) {
                const real_T configured_mass = static_cast<real_T>(vehicle_child.getFloat("Mass", params.mass));
                if (configured_mass > 0) {
                    params.mass = configured_mass;

                    const real_T motor_assembly_weight = 0.055f;
                    const real_T box_mass = params.mass - params.rotor_count * motor_assembly_weight;
                    computeInertiaMatrix(params.inertia, params.body_box, params.rotor_poses, box_mass, motor_assembly_weight);
                }
            }
        }

        virtual const SensorFactory* getSensorFactory() const override
        {
            return sensor_factory_.get();
        }

    private:
        const AirSimSettings::VehicleSetting* vehicle_setting_; //store as pointer because of derived classes
        std::shared_ptr<const SensorFactory> sensor_factory_;
    };
}
} //namespace
#endif
