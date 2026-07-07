FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://platform-top.h file://bsp.cfg"
SRC_URI += "file://user_2026-05-27-08-51-00.cfg \
            file://user_2026-05-29-10-20-00.cfg \
            file://user_2026-06-02-07-24-00.cfg \
            file://user_2026-06-05-10-43-00.cfg \
            "

