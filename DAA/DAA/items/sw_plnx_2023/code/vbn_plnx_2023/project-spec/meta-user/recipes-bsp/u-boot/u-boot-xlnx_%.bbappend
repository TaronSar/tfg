FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI:append = " file://platform-top.h file://bsp.cfg"
SRC_URI += "file://user_2025-08-19-15-50-00.cfg \
            file://user_2025-08-26-09-44-00.cfg \
            file://0001-dfu-Add-proper-dependency-for-CONFIG_DFU_MMC.patch \
            file://0002-cmd-thordown-Add-proper-dependency-for-CMD_THOR_DOWN.patch \
    	    file://0003-zynqmp-config-Add-proper-dependencies-for-USB.patch \ 
            "

