#include <wrappers/Location.h>
#include <Fixedqueue_std.h>
#include <Camerapinhole.h>
#include <markers/Markerframetracker_cv.h>
#include <Extrinsics_cv.h>
#include <Arucoparser.h>
#include <vector>
#include <opencv2/aruco.hpp>
#include <Cvtools.h>
#include <opencv2/opencv.hpp>
#include <Simple_config_parser.h>
#include <iostream>

namespace Vbn
{
    typedef std::vector<Vbn::Marker> Markers;
    typedef std::vector<uint8_t> Ids;

    // Definición de la clase Impl
    class Location_wrapper::Impl
    {
        public:
            Impl(const std::string& camera_settings, const std::string& aruco_settings, const uint8_t& dictionary_size, const float& global_rot) :
                    cameraParser(Vbn::Simple_config_parser::get_instance()),
                    aruco_parser(aruco_settings, dictionary_size, global_rot),
                    //extrinsics((Icameramodel<float, float, uint16_t>*)camera_pinhole),
                    dictionary(cv::aruco::getPredefinedDictionary(cv::aruco::DICT_6X6_250)),
                    frame_counter(0),
                    camera_pinhole(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 10050),
                    global_rot(global_rot)
            {
                Base::Memmgr::get_instance().get_allocator(Base::Memmgr::external);
                float fx, fy, cx, cy, p1, p2, k1, k2, k3;

                cameraParser.init(camera_settings);

                cameraParser.GetCameraFX(fx);
                cameraParser.GetCameraFY(fy);
                cameraParser.GetCameraCX(cx);
                cameraParser.GetCameraCY(cy);
                cameraParser.GetCameraK1(k1);
                cameraParser.GetCameraK2(k2);
                cameraParser.GetCameraP1(p1);
                cameraParser.GetCameraP2(p2);
                cameraParser.GetCameraK3(k3);
                // cameraParser.GetCameraK4(k4);

                cameraParser.GetCameraWidth(width);
                cameraParser.GetCameraHeight(height);

                camera_pinhole.set_model(fx, fy, cx, cy, k1, k2, p1, p2, k3);
                extrinsics = new Extrinsics(&camera_pinhole);

                K_matrix = (cv::Mat_<double>(3, 3) << fx, 0, cx, 0, fy, cy, 0,  0,  1);
                D_matrix = (cv::Mat_<double>(5, 1) << k1, k2, p1, p2, k3);
            }

            ~Impl()
            {
                delete extrinsics;
            }

            void undistort(void* image)
            {
                cv::Mat img(height, width, CV_8UC1, image);
                cv::Mat auxImg = img.clone();
                // cv::fisheye::undistortImage(auxImg, img, K_matrix, D_matrix, K_matrix, img.size());
                cv::undistort(auxImg, img, K_matrix, D_matrix, K_matrix);
            }

            bool locate(void* image, Eigen::Matrix3f& R, Eigen::Vector3f& t)
            {
                cv::Mat img(height, width, CV_8UC1, image);

                // Preprocess recieved image to improve aruco detection
                cv::Mat thresh_img;
                threshold(img, thresh_img, 180, 180, cv::THRESH_TRUNC); 
                cv::Mat closed;
                cv::Mat element = getStructuringElement(cv::MORPH_RECT, cv::Size(3, 3));
                morphologyEx(thresh_img, closed, cv::MORPH_CLOSE, element);
                morphologyEx(closed, img, cv::MORPH_OPEN, element);

                Vbn::U8vgaframe* frame;
                Markers markers;
                Ids ids_frame;
                cv::aruco::detectMarkers(img, dictionary, markers, ids_frame);
                std::cout << "num markers: " << markers.size() << ", ";
                if (!ids_frame.empty())
                {
                    std::vector<int> int_ids;
                    for (int i = 0; i < ids_frame.size(); i++)
                    {
                        int_ids.push_back(static_cast<int>(ids_frame[i]));
                    }
                    cv::aruco::drawDetectedMarkers(img, markers, int_ids);
                } 
                cv::imshow("Test", img);
                cv::waitKey(1);
                if(markers.size()==0)
                {
                    return false;
                }
                fq_cvmat.push(img);
                fq_markers.push(markers);
                fq_ids.push(ids_frame);

                Vbn::Cvtools::cv_bridge(fq_cvmat.back(), frame_counter++, frame);
                
                if(fq_cvmat.size()<2)
                {
                    fq_frames.push(frame);
                    frame_tracker.push(fq_frames.back(), &fq_markers.back(), &fq_ids.back());
                    return false;
                }
                else
                {
                    fq_frames.push(frame);
                    frame_tracker.push(fq_frames.back(), &fq_markers.back(), &fq_ids.back());
                }

                std::vector<cv::Point2f> v_p1, v_p2;
                std::vector<uint8_t> ids;
                frame_tracker.get_tracked_points(v_p1, v_p2, ids);
                if(v_p1.size() == 0)
                {
                    return false;
                }

                std::vector<Eigen::Vector3f> corners;

                aruco_parser.get_corners(ids, corners);
                if (corners.size() == 0)
                {
                    return false;
                }
                extrinsics->compute_extrinsics(v_p2, corners, R, t);

                bool ok = true;
                if(t.hasNaN())
                {
                    t = Eigen::Vector3f();
                    ok = false;
                }
                if(R.hasNaN())
                {
                    R = Eigen::Matrix3f::Identity();
                    ok = false;
                }

                // Rotate to match global reference system
                if (ok)
                {
                    float theta = global_rot * M_PI / 180.0f;
                    Eigen::Matrix3f Rz;
                    Rz <<   std::cos(theta), -std::sin(theta), 0,
                            std::sin(theta),  std::cos(theta), 0,
                                0,                0,          1;
                    R = Rz * R;
                }

                return ok;
            }

        private:

            cv::Ptr<cv::aruco::Dictionary> dictionary;

            Fixedqueue<cv::Mat,2> fq_cvmat;
            Fixedqueue<std::vector<Vbn::Marker>,2> fq_markers;
            Fixedqueue<std::vector<uint8_t>,2> fq_ids;
            Fixedqueue<Vbn::U8vgaframe*,2> fq_frames;
            Markerframetracker frame_tracker;
            Rcamerapinhole camera_pinhole;
            Extrinsics* extrinsics;

            Arucoparser aruco_parser;
            Simple_config_parser& cameraParser;

            int width;
            int height;

            unsigned int frame_counter;

            cv::Mat K_matrix;
            cv::Mat D_matrix;

            float global_rot;
    };

    Location_wrapper::Location_wrapper(
        const std::string& camera_settings,
        const std::string& aruco_settings,
        const uint8_t& dictionary_size,
        const float &global_rot)
    {
        //pImpl = new Impl(fx, fy, cx, cy, k1, k2, p1, p2, k3);
        pImpl = new Impl(camera_settings, aruco_settings, dictionary_size, global_rot);
    };

    void Location_wrapper::undistort(void* image)
    {
        pImpl->undistort(image);
    };

    bool Location_wrapper::locate(void* image, Eigen::Matrix3f& R, Eigen::Vector3f& t){
        return pImpl->locate(image, R, t);
    };
}
