// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#ifndef msr_airlib_AirSimVeronteEstimator_hpp
#define msr_airlib_AirSimVeronteEstimator_hpp

#include "firmware/interfaces/CommonStructs.hpp"
#include "AirSimVeronteCommon.hpp"
#include "physics/Kinematics.hpp"
#include "physics/Environment.hpp"
#include "common/Common.hpp"

namespace msr
{
namespace airlib
{

    class AirSimVeronteEstimator : public veronte::IStateEstimator
    {
    public:
        virtual ~AirSimVeronteEstimator() {}

        //for now we don't do any state estimation and use ground truth (i.e. assume perfect sensors)
        void setGroundTruthKinematics(const Kinematics::State* kinematics, const Environment* environment)
        {
            kinematics_ = kinematics;
            environment_ = environment;
        }

        virtual veronte::Axis3r getAngles() const override
        {
            veronte::Axis3r angles;
            VectorMath::toEulerianAngle(kinematics_->pose.orientation,
                                        angles.pitch(),
                                        angles.roll(),
                                        angles.yaw());

            //Utils::log(Utils::stringf("Ang Est:\t(%f, %f, %f)", angles.pitch(), angles.roll(), angles.yaw()));

            return angles;
        }

        virtual veronte::Axis3r getAngularVelocity() const override
        {
            const auto& anguler = kinematics_->twist.angular;

            veronte::Axis3r conv;
            conv.x() = anguler.x();
            conv.y() = anguler.y();
            conv.z() = anguler.z();

            return conv;
        }

        virtual veronte::Axis3r getPosition() const override
        {
            return AirSimVeronteCommon::toAxis3r(kinematics_->pose.position);
        }

        virtual veronte::Axis3r transformToBodyFrame(const veronte::Axis3r& world_frame_val) const override
        {
            const Vector3r& vec = AirSimVeronteCommon::toVector3r(world_frame_val);
            const Vector3r& trans = VectorMath::transformToBodyFrame(vec, kinematics_->pose.orientation);
            return AirSimVeronteCommon::toAxis3r(trans);
        }

        virtual veronte::Axis3r getLinearVelocity() const override
        {
            return AirSimVeronteCommon::toAxis3r(kinematics_->twist.linear);
        }

        virtual veronte::Axis4r getOrientation() const override
        {
            return AirSimVeronteCommon::toAxis4r(kinematics_->pose.orientation);
        }

        virtual veronte::GeoPoint getGeoPoint() const override
        {
            return AirSimVeronteCommon::toVeronteGeoPoint(environment_->getState().geo_point);
        }

        virtual veronte::GeoPoint getHomeGeoPoint() const override
        {
            return AirSimVeronteCommon::toVeronteGeoPoint(environment_->getHomeGeoPoint());
        }

        virtual veronte::KinematicsState getKinematicsEstimated() const override
        {
            veronte::KinematicsState state;
            state.position = getPosition();
            state.orientation = getOrientation();
            state.linear_velocity = getLinearVelocity();
            state.angular_velocity = getAngularVelocity();
            state.linear_acceleration = AirSimVeronteCommon::toAxis3r(kinematics_->accelerations.linear);
            state.angular_acceleration = AirSimVeronteCommon::toAxis3r(kinematics_->accelerations.angular);

            return state;
        }

    private:
        const Kinematics::State* kinematics_;
        const Environment* environment_;
    };
}
} //namespace
#endif
