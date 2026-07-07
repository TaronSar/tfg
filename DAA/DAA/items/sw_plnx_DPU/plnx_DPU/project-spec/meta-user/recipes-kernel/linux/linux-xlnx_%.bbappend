FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append = " file://bsp.cfg"
KERNEL_FEATURES:append = " bsp.cfg"
SRC_URI += "file://user_2025-08-20-12-20-00.cfg \
            file://user_2025-08-20-12-45-00.cfg \
            file://user_2025-08-25-10-18-00.cfg \
            "

