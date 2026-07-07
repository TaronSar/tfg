#include <mutex>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <liborb_coproc.h>
#include <opencv2/opencv.hpp>

// Defined in liborb_coproc_dummy.cpp
extern const std::string& get_image_path();
extern void set_image_path(const std::string&);

PYBIND11_MODULE(liborb_coproc_wrapper, m)
{
    m.def("set_image_path", &set_image_path, "Set image directory path");
    pybind11::class_<ORB_coproc>(m, "ORB_coproc", pybind11::module_local())
        .def_static("get_instance", &ORB_coproc::get_instance, pybind11::return_value_policy::reference)
        .def_static("initialize", &ORB_coproc::initialize,
            pybind11::arg("width"),
            pybind11::arg("height"),
            pybind11::arg("shs"),
            pybind11::arg("gain"),
            pybind11::arg("camera")
        )
        .def("get_camera_frame", [](ORB_coproc& self) {
            void* ptr = self.get_camera_frame();
            if (!ptr)
                throw std::runtime_error("Failed to get camera frame");

            int w = self.get_img_width();
            int h = self.get_img_height();
            return pybind11::array_t<uint8_t>({h, w, 3}, static_cast<uint8_t*>(ptr));
            // return pybind11::array_t<uint8_t>({h, w, 3}, img.data);
        });
}