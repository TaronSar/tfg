#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DEST_DIR="/media/ejn3@ad.embention.com/04C4-8948/" # 2GB FAT32

if [ ! -d "${DEST_DIR}" ]; then
    echo "Asegúrate de que la tarjeta SD esté conectada y montada en: ${DEST_DIR}"
    exit 1
fi

echo "Limpiando archivos .BIN antiguos de la tarjeta SD..."
rm -f "${DEST_DIR}"*.BIN
rm -f "${DEST_DIR}"*.scr
rm -f "${DEST_DIR}"*.ub

echo "Copiando nuevos archivos .BIN..."
cp -f "${ROOT_DIR}/project/scripts/bootgen/BOOT.BIN" "${DEST_DIR}/BOOT.BIN"
cp -f "${ROOT_DIR}/project/scripts/bootgen/BOOT0001.BIN" "${DEST_DIR}/BOOT0001.BIN"
cp -f "${ROOT_DIR}/project/scripts/bootgen/BOOT0002.BIN" "${DEST_DIR}/BOOT0002.BIN"
cp -f "${ROOT_DIR}/project/plnx/BOOT0003.BIN" "${DEST_DIR}/BOOT0003.BIN"
cp -f "${ROOT_DIR}/project/plnx/boot.scr" "${DEST_DIR}/boot.scr"
cp -f "${ROOT_DIR}/project/plnx/image.ub" "${DEST_DIR}/image.ub"

echo "DONE"