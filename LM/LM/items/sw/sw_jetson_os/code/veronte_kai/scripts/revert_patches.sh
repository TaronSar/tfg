#!/usr/bin/env bash
# revert_patches.sh — Revierte todos los parches de veronte_kai/patches/ con quilt
# Si quilt pop falla, restaura los archivos desde backups/.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LDK_DIR="$(cd "$VK_DIR/.." && pwd)/Linux_for_Tegra"

[[ -f "$LDK_DIR/flash.sh" ]] || { echo "ERROR: No se encuentra $LDK_DIR/flash.sh"; exit 1; }

echo "Revirtiendo parches en $LDK_DIR ..."

quilt_failed=0
(
    export QUILT_PATCHES="$VK_DIR/patches"
    export QUILT_SERIES="$VK_DIR/patches/series"
    cd "$LDK_DIR"
    quilt pop -a -f || true
) || quilt_failed=1

if [[ $quilt_failed -eq 1 ]]; then
    echo "ADVERTENCIA: quilt pop -a falló. Restaurando desde backups..."
fi

# Restaurar desde backups si existen
latest_backup=$(ls -1dt "$VK_DIR/backups"/Linux_for_Tegra_* 2>/dev/null | head -1 || true)

if [[ -n "$latest_backup" ]]; then
    echo "Restaurando desde: $latest_backup"
    while IFS= read -r -d '' file; do
        rel="${file#$latest_backup/}"
        dst="$LDK_DIR/$rel"
        echo "  Restaurando: $rel"
        mkdir -p "$(dirname "$dst")"
        cp -p "$file" "$dst"
    done < <(find "$latest_backup" -type f -print0)
    echo "Restauración desde backup completada."
else
    echo "No se encontraron backups en $VK_DIR/backups/."
    [[ $quilt_failed -eq 1 ]] && echo "ADVERTENCIA: quilt falló y no hay backups. Revisa manualmente." || true
fi

# Eliminar marcador
if [[ -f "$LDK_DIR/.veronte_applied" ]]; then
    rm "$LDK_DIR/.veronte_applied"
    echo "Marcador .veronte_applied eliminado."
fi

# Eliminar estado de quilt
rm -rf "$LDK_DIR/.pc"

echo "Reversión completada."
