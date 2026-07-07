#!/usr/bin/env bash
# build_veronte_kai.sh — Orquestador principal del build para la carrier Veronte Kai
# Jetson Orin Nano P3767-0003 | L4T R36.5.0 (JetPack 6.0)
#
# Uso:
#   ./build_veronte_kai.sh [opciones]
#
# Opciones:
#   --clean          Revertir parches y borrar artefactos antes de compilar
#   --skip-patch     Saltarse Stage 2 (los parches ya están aplicados)
#   --only-stage N   Ejecutar solo el stage N (1, 2, 3 o 4)
#   --dry-run        Simular todas las operaciones sin modificar nada
#   --diagnose       Mostrar información de diagnóstico del entorno y salir
#   -h, --help       Mostrar esta ayuda

set -euo pipefail
IFS=$'\n\t'

# ── Rutas ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export VK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export LDK_DIR="$(cd "$VK_DIR/.." && pwd)/Linux_for_Tegra"
export BUILD_TS
BUILD_TS="$(date +%Y%m%d_%H%M%S)"

# ── Valores por defecto ────────────────────────────────────────────────────────
CLEAN=0
SKIP_PATCH=0
ONLY_STAGE=""
DRY_RUN=0
DIAGNOSE=0

export SKIP_PATCH DRY_RUN

# ── Colores (solo si stdout es terminal) ──────────────────────────────────────
if [[ -t 1 ]]; then
    C_RESET='\033[0m'; C_GREEN='\033[0;32m'; C_YELLOW='\033[1;33m'; C_RED='\033[0;31m'; C_CYAN='\033[0;36m'
else
    C_RESET=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_CYAN=''
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
log()  { echo -e "${C_GREEN}[BUILD]${C_RESET} $*"; }
warn() { echo -e "${C_YELLOW}[WARN]${C_RESET}  $*" >&2; }
die()  { echo -e "${C_RED}[ERROR]${C_RESET} $*" >&2; exit 1; }
export -f log warn die

# ── Parseo de argumentos ──────────────────────────────────────────────────────
usage() {
    grep '^#' "$0" | grep -v '#!/' | sed 's/^# \{0,1\}//' | head -20
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --clean)        CLEAN=1 ;;
        --skip-patch)   SKIP_PATCH=1; export SKIP_PATCH ;;
        --only-stage)   ONLY_STAGE="$2"; shift ;;
        --dry-run)      DRY_RUN=1; export DRY_RUN ;;
        --diagnose)     DIAGNOSE=1 ;;
        -h|--help)      usage ;;
        *) die "Opción desconocida: $1. Usa --help para ver la ayuda." ;;
    esac
    shift
done

# ── Cargar librerías de stages ────────────────────────────────────────────────
LIB_DIR="$SCRIPT_DIR/lib"
# shellcheck source=lib/stage1_setup.sh
source "$LIB_DIR/stage1_setup.sh"
# shellcheck source=lib/stage2_patching.sh
source "$LIB_DIR/stage2_patching.sh"
# shellcheck source=lib/stage3_rootfs_prep.sh
source "$LIB_DIR/stage3_rootfs_prep.sh"
# shellcheck source=lib/stage4_flash_wrapper.sh
source "$LIB_DIR/stage4_flash_wrapper.sh"

# ── Log a archivo ─────────────────────────────────────────────────────────────
mkdir -p "$VK_DIR/out"
LOG_FILE="$VK_DIR/out/build_${BUILD_TS}.log"

# A partir de aquí, todo se escribe también al log (sin afectar colores en consola)
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "  Veronte Kai Build System"
echo "  $(date)"
echo "  VK_DIR:  $VK_DIR"
echo "  LDK_DIR: $LDK_DIR"
echo "  BUILD_TS: $BUILD_TS"
[[ "$DRY_RUN" == "1" ]] && echo "  MODO: DRY-RUN (sin cambios reales)"
echo "=========================================="

# Solicitar credenciales sudo una sola vez al principio
# (Stage 3 necesita sudo para modificar rootfs/boot/extlinux/extlinux.conf,
#  que es propiedad de root tras apply_binaries.sh)
if [[ "${DRY_RUN:-0}" == "0" ]]; then
    echo "Este script necesita sudo para modificar archivos del rootfs (extlinux.conf)."
    sudo -v || die "Se requieren permisos sudo para continuar."
fi

# ── Diagnóstico ───────────────────────────────────────────────────────────────
if [[ "$DIAGNOSE" == "1" ]]; then
    log "=== Diagnóstico del entorno ==="
    log "LDK_DIR: $LDK_DIR"
    log "VK_DIR:  $VK_DIR"
    echo ""
    log "Paquetes del host:"
    for cmd in qemu-aarch64-static lz4 xmllint dtc quilt python3; do
        if command -v "$cmd" &>/dev/null; then
            log "  OK: $cmd → $(command -v "$cmd")"
        else
            warn "  FALTA: $cmd"
        fi
    done
    echo ""
    log "Archivos BSP clave:"
    for f in flash.sh apply_binaries.sh rootfs/etc/nv_tegra_release \
              bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi \
              bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts \
              rootfs/boot/extlinux/extlinux.conf; do
        if [[ -e "$LDK_DIR/$f" ]]; then
            log "  OK: $f"
        else
            warn "  FALTA: $f"
        fi
    done
    echo ""
    log "Estado de parches:"
    if [[ -f "$LDK_DIR/.veronte_applied" ]]; then
        log "  Parches APLICADOS:"
        cat "$LDK_DIR/.veronte_applied" | while read -r line; do log "    $line"; done
    else
        log "  Parches NO aplicados."
    fi
    echo ""
    log "EEPROM bypass (informativo):"
    local mb2_bct="$LDK_DIR/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts"
    if [[ -f "$mb2_bct" ]]; then
        grep -E 'cvm_eeprom_read_size|cvb_eeprom_read_size' "$mb2_bct" | while read -r l; do log "  $l"; done
    fi
    exit 0
fi

# ── Acción --clean ────────────────────────────────────────────────────────────
if [[ "$CLEAN" == "1" ]]; then
    log "=== --clean: Revirtiendo estado previo ==="
    if [[ "$DRY_RUN" == "0" ]]; then
        "$SCRIPT_DIR/revert_patches.sh" || warn "revert_patches.sh terminó con errores (continuando)"
        rm -rf "$LDK_DIR/bootloader/signed" "$LDK_DIR/bootloader/p3768" 2>/dev/null || true
        rm -f "$VK_DIR/scripts/flash_veronte_kai.sh" 2>/dev/null || true
        log "  Limpieza completada."
    else
        log "  [DRY-RUN] Se ejecutaría revert_patches.sh y se borrarían artefactos."
    fi
fi

# ── Ejecutar stages ───────────────────────────────────────────────────────────
run_stage() {
    local n="$1"
    if [[ -n "$ONLY_STAGE" && "$ONLY_STAGE" != "$n" ]]; then
        log "Saltando Stage $n (--only-stage $ONLY_STAGE activo)."
        return
    fi
    case "$n" in
        1) stage1_setup ;;
        2) stage2_patching ;;
        3) stage3_rootfs_prep ;;
        4) stage4_flash_wrapper ;;
        *) die "Stage desconocido: $n" ;;
    esac
}

run_stage 1
run_stage 2
run_stage 3
run_stage 4

echo ""
echo "=========================================="
echo "  Build finalizado correctamente."
echo "  Log: $LOG_FILE"
echo "=========================================="
