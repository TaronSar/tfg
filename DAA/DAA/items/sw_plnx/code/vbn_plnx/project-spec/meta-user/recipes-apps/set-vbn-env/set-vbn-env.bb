#
# This file is the set-vbn-env recipe.
#

SUMMARY = "Simple set-vbn-env application"
SECTION = "PETALINUX/apps"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://set-vbn-env \
	"

S = "${WORKDIR}"

FILESEXTRAPATHS_prepend := "${THISDIR}/files:"

inherit update-rc.d

INITSCRIPT_NAME = "set-vbn-env"
INITSCRIPT_PARAMS = "start 99 S ."

do_install() {
	     install -d ${D}${sysconfdir}/init.d
	     install -m 0755 ${WORKDIR}/set-vbn-env ${D}${sysconfdir}/init.d/set-vbn-env
}
FILES_${PN} += "${sysconfdir}/*"
