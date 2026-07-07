#!/usr/bin/env bash
# Stage 1 — Setup y verificaciones previas
# Verifica el entorno host antes de tocar nada del BSP.
# Llamado por build_veronte_kai.sh; NO ejecutar directamente.
set -euo pipefail
IFS=$'\n\t'

# Variables inyectadas por el orquestador:
#   LDK_DIR, VK_DIR, BUILD_TS, DRY_RUN

stage1_setup() {
    log "=== Stage 1: Setup ==="

    # 1. Verificar BSP
    log "Verificando BSP en: $LDK_DIR"
    [[ -f "$LDK_DIR/flash.sh" ]] || die "No se encuentra $LDK_DIR/flash.sh. ¿Está el BSP correctamente extraído?"

    local l4t_release=""
    if [[ -f "$LDK_DIR/rootfs/etc/nv_tegra_release" ]]; then
        l4t_release=$(head -1 "$LDK_DIR/rootfs/etc/nv_tegra_release")
        log "L4T release: $l4t_release"
        if ! echo "$l4t_release" | grep -q "R36"; then
            warn "ADVERTENCIA: Se esperaba L4T R36.x (JetPack 6.0), encontrado: $l4t_release"
        fi
    else
        warn "No se encontró rootfs/etc/nv_tegra_release — ¿se aplicó apply_binaries.sh?"
    fi

    # 2. Verificar rootfs
    log "Verificando rootfs..."
    if [[ ! -d "$LDK_DIR/rootfs/etc" ]]; then
        die "El directorio rootfs/ está vacío o incompleto.
Por favor ejecuta primero:
  cd $LDK_DIR
  sudo ./apply_binaries.sh
y luego vuelve a ejecutar este script."
    fi

    # 3. Verificar paquetes del host
    log "Verificando paquetes del host..."
    local missing_pkgs=()
    local required_cmds=(
        "qemu-aarch64-static:qemu-user-static"
        "lz4:lz4"
        "xmllint:libxml2-utils"
        "dtc:device-tree-compiler"
        "quilt:quilt"
        "python3:python3"
    )
    for entry in "${required_cmds[@]}"; do
        local cmd="${entry%%:*}"
        local pkg="${entry##*:}"
        if ! command -v "$cmd" &>/dev/null; then
            missing_pkgs+=("$pkg")
            warn "  Falta: $cmd (paquete: $pkg)"
        else
            log "  OK: $cmd"
        fi
    done

    if [[ ${#missing_pkgs[@]} -gt 0 ]]; then
        local install_cmd="sudo apt-get install -y ${missing_pkgs[*]}"
        if [[ "${DRY_RUN:-0}" == "1" ]]; then
            warn "  [DRY-RUN] Faltan paquetes (no bloqueante en dry-run):"
            warn "  $install_cmd"
        else
            die "Faltan paquetes del host. Instálalos con:
  $install_cmd"
        fi
    fi

    # 4. Verificar que quilt no tiene parches a medias
    if [[ -f "$LDK_DIR/.veronte_applied" ]]; then
        warn "Detectado marcador .veronte_applied — los parches ya fueron aplicados."
        warn "Usa --skip-patch para continuar o --clean para revertir."
    fi

    # 5. Crear directorio out/
    mkdir -p "$VK_DIR/out"
    log "Build timestamp: $BUILD_TS"
    log "Log: $VK_DIR/out/build_${BUILD_TS}.log"

    log "Stage 1 completado OK."
}
