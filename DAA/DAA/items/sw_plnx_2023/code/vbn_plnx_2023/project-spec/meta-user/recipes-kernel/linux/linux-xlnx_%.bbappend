FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append = " file://bsp.cfg"
KERNEL_FEATURES:append = " bsp.cfg"
SRC_URI += "file://user_2025-08-19-15-31-00.cfg \
            file://user_2025-08-19-15-59-00.cfg \
            file://user_2025-08-25-13-38-00.cfg \
            file://user_2025-08-26-14-17-00.cfg \
            "

