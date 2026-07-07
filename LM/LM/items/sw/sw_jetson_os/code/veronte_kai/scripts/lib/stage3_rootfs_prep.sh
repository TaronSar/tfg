#!/usr/bin/env bash
# Stage 3 — Preparación del RootFS / Boot config para /dev/sda1
# Llamado por build_veronte_kai.sh; NO ejecutar directamente.
set -euo pipefail
IFS=$'\n\t'

stage3_rootfs_prep() {
    log "=== Stage 3: RootFS/Boot config ==="

    _patch_extlinux
    _check_cmdline_in_conf
    _optional_fstab

    log "Stage 3 completado OK."
}

_patch_extlinux() {
    local extlinux="$LDK_DIR/rootfs/boot/extlinux/extlinux.conf"

    if [[ ! -f "$extlinux" ]]; then
        warn "extlinux.conf no existe en $extlinux"
        warn "Esto es normal si apply_binaries.sh aún no se ha ejecutado."
        return
    fi

    log "Verificando extlinux.conf (archivo propiedad de root) ..."

    # Si ya tiene el cambio, solo validar
    if grep -qE 'root=/dev/sda1.*rootwait' "$extlinux"; then
        log "  OK: extlinux.conf ya tiene root=/dev/sda1 rootwait."
        return
    fi

    # Aplicar con sudo (extlinux.conf es root:root desde apply_binaries.sh)
    log "  Aplicando root=/dev/sda1 rootwait con sudo ..."
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        # Backup antes de tocar (con sudo si es necesario)
        sudo cp -p "$extlinux" "${extlinux}.veronte_bak"

        sudo sed -i \
            's/\(      APPEND \${cbootargs}\)$/\1 root=\/dev\/sda1 rootwait/' \
            "$extlinux"

        # Verificar resultado
        if grep -qE 'root=/dev/sda1.*rootwait' "$extlinux"; then
            log "  OK: extlinux.conf actualizado correctamente."
        else
            die "No se pudo actualizar extlinux.conf. Edita manualmente: $extlinux"
        fi
    else
        log "  [DRY-RUN] Se ejecutaría: sudo sed -i ... $extlinux"
    fi
}

_check_cmdline_in_conf() {
    local vk_conf="$LDK_DIR/veronte_kai.conf"

    if [[ ! -f "$vk_conf" ]]; then
        warn "  veronte_kai.conf no encontrado en $LDK_DIR"
        warn "  Asegúrate de que el parche 0002 fue aplicado (Stage 2)."
        return
    fi

    log "Verificando CMDLINE_ADD en veronte_kai.conf ..."
    if grep -q 'CMDLINE_ADD.*root=/dev/sda1' "$vk_conf"; then
        log "  OK: CMDLINE_ADD contiene root=/dev/sda1"
    else
        warn "  ADVERTENCIA: CMDLINE_ADD en veronte_kai.conf no contiene root=/dev/sda1"
        warn "  Revisa $vk_conf"
    fi

    if grep -q 'rootwait' "$vk_conf"; then
        log "  OK: rootwait presente en veronte_kai.conf"
    else
        warn "  ADVERTENCIA: rootwait no encontrado en veronte_kai.conf"
    fi
}

_optional_fstab() {
    local fstab="$LDK_DIR/rootfs/etc/fstab"

    if [[ ! -f "$fstab" ]]; then
        warn "  fstab no encontrado — saltando (normal si rootfs no está preparado)."
        return
    fi

    log "Revisando fstab ..."
    if grep -q '/dev/sda1' "$fstab"; then
        log "  OK: fstab ya tiene entrada para /dev/sda1"
    else
        log "  INFO: fstab no tiene entrada explícita para /dev/sda1."
        log "  El boot desde /dev/sda1 funciona con la línea APPEND+rootwait."
        log "  Si necesitas una entrada fstab estática, añade manualmente:"
        log "    /dev/sda1  /  ext4  defaults,noatime  0  1"
    fi
}
