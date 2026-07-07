#!/usr/bin/env bash
# apply_patches.sh — Aplica todos los parches de veronte_kai/patches/ con quilt
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LDK_DIR="$(cd "$VK_DIR/.." && pwd)/Linux_for_Tegra"

[[ -f "$LDK_DIR/flash.sh" ]] || { echo "ERROR: No se encuentra $LDK_DIR/flash.sh"; exit 1; }
[[ -f "$VK_DIR/patches/series" ]] || { echo "ERROR: No se encuentra $VK_DIR/patches/series"; exit 1; }

if [[ -f "$LDK_DIR/.veronte_applied" ]]; then
    echo "ADVERTENCIA: Los parches ya están aplicados (.veronte_applied existe)."
    echo "Usa revert_patches.sh para revertir antes de aplicar de nuevo."
    exit 1
fi

echo "Aplicando parches en $LDK_DIR ..."
(
    export QUILT_PATCHES="$VK_DIR/patches"
    export QUILT_SERIES="$VK_DIR/patches/series"
    cd "$LDK_DIR"
    quilt push -a
)

echo "applied_at=$(date +%Y%m%d_%H%M%S)" > "$LDK_DIR/.veronte_applied"
echo "Parches aplicados correctamente."
