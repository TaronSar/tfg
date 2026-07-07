#!/bin/bash
set -euo pipefail

SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${SCRIPTDIR}/bootgen"   # lo deja en la carpeta scripts

ROOT_DIR="$(cd "${SCRIPTDIR}/../.." && pwd)"

PMUFW="$(ls -1 "${ROOT_DIR}/platform/zynqmp_pmufw"/pmufw*.elf 2>/dev/null | head -n1 || true)"
FSBL="${ROOT_DIR}/platform/export/platform/sw/platform/boot/fsbl.elf"
BIT="${ROOT_DIR}/platform/hw/design_1_wrapper.bit"
APP_BOOTLOADER="${ROOT_DIR}/project/cmake/build/bootloader.elf"
APP_0001="${ROOT_DIR}/project/cmake/build0001/0001.elf"
APP_0002="${ROOT_DIR}/project/cmake/build0002/0002.elf"

command -v bootgen >/dev/null || { echo "ERROR: bootgen no está en el PATH"; exit 1; }
[[ -f "${FSBL}" ]] || { echo "ERROR: FSBL no encontrado: ${FSBL}"; exit 1; }
[[ -f "${BIT}"  ]] || { echo "ERROR: Bitstream no encontrado: ${BIT}"; exit 1; }
[[ -f "${APP_BOOTLOADER}"  ]] || { echo "ERROR: App no encontrada: ${APP_BOOTLOADER}"; exit 1; }
[[ -f "${APP_0001}"  ]] || { echo "ERROR: App 1 no encontrada: ${APP_0001}"; exit 1; }
[[ -f "${APP_0002}"  ]] || { echo "ERROR: App 2 no encontrada: ${APP_0002}"; exit 1; }
if [[ -z "${PMUFW}" || ! -f "${PMUFW}" ]]; then
  echo "ERROR: pmufw.elf no encontrado en platform/zynqmp_pmufw"
  exit 1
fi

echo "Usando:"
echo "  PMUFW : ${PMUFW}"
echo "  FSBL  : ${FSBL}"
echo "  BIT   : ${BIT}"
echo "  APP_BOOTLOADER   : ${APP_BOOTLOADER}"

# Directorio temporal SIN '@'
TMPDIR="$(mktemp -d "/tmp/bootgen_tmp.XXXXXX")"
echo "Trabajando en: ${TMPDIR}"

cp -f "${PMUFW}" "${TMPDIR}/pmufw.elf"
cp -f "${FSBL}"  "${TMPDIR}/fsbl.elf"
cp -f "${BIT}"   "${TMPDIR}/design.bit"
cp -f "${APP_BOOTLOADER}"   "${TMPDIR}/bootloader.elf"
cp -f "${APP_0001}"   "${TMPDIR}/0001.elf"
cp -f "${APP_0002}"   "${TMPDIR}/0002.elf"
cp -f "${ROOT_DIR}/project/scripts/bootgen/boot.bif"   "${TMPDIR}/boot.bif"
cp -f "${ROOT_DIR}/project/scripts/bootgen/boot0001.bif"   "${TMPDIR}/boot0001.bif"
cp -f "${ROOT_DIR}/project/scripts/bootgen/boot0002.bif"   "${TMPDIR}/boot0002.bif"

( cd "${TMPDIR}" && bootgen -arch zynqmp -image boot.bif -o BOOT.BIN -w )
( cd "${TMPDIR}" && bootgen -arch zynqmp -image boot0001.bif -o BOOT0001.BIN -w )
( cd "${TMPDIR}" && bootgen -arch zynqmp -image boot0002.bif -o BOOT0002.BIN -w )

cp -f "${TMPDIR}/BOOT.BIN" "${DEST_DIR}/BOOT.BIN"
cp -f "${TMPDIR}/BOOT0001.BIN" "${DEST_DIR}/BOOT0001.BIN"
cp -f "${TMPDIR}/BOOT0002.BIN" "${DEST_DIR}/BOOT0002.BIN"
echo "OK: Generado ${DEST_DIR}/BOOT.BIN"
echo "OK: Generado ${DEST_DIR}/BOOT0001.BIN"
echo "OK: Generado ${DEST_DIR}/BOOT0002.BIN"

rm -rf "${TMPDIR}"
