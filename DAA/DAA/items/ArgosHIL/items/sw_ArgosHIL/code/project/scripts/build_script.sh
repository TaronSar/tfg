#!/bin/bash
# Orquesta el build completo: vlibs -> wvlibs -> HIL
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}"

echo "############################################"
echo "# 1/3  Vlibs"
echo "############################################"
bash ./build_vlibs.sh

echo "############################################"
echo "# 2/3  wvlibs (libwvlibs.a)"
echo "############################################"
bash ./build_wvlibs.sh

echo "############################################"
echo "# 3/3  HIL"
echo "############################################"
bash ./build.sh

echo "==> Build completo OK"
