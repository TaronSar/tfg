FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI:append = " file://bsp.cfg"
KERNEL_FEATURES:append = " bsp.cfg"
SRC_URI += "file://user_2026-05-27-08-22-00.cfg \
            file://user_2026-05-29-10-23-00.cfg \
            file://user_2026-06-02-07-19-00.cfg \
            file://user_2026-06-02-15-45-00.cfg \
            file://user_2026-06-05-10-27-00.cfg \
            file://user_2026-06-05-11-25-00.cfg \
            file://user_2026-06-05-11-42-00.cfg \
            file://user_2026-06-09-06-42-00.cfg \
            file://dwc3.patch \
            file://user_2026-06-09-10-35-00.cfg \
            file://user_2026-06-10-09-26-00.cfg \
            file://user_2026-06-10-12-18-00.cfg \
            file://user_2026-06-10-13-52-00.cfg \
            "

