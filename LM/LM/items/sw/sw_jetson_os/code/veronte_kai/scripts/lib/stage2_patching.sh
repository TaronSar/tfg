#!/usr/bin/env bash
# Stage 2 — Patching: backup + quilt push + validaciones
# Llamado por build_veronte_kai.sh; NO ejecutar directamente.
set -euo pipefail
IFS=$'\n\t'

stage2_patching() {
    log "=== Stage 2: Patching ==="

    local backup_dir="$VK_DIR/backups/Linux_for_Tegra_${BUILD_TS}"
    local applied_marker="$LDK_DIR/.veronte_applied"

    # Comprobar si ya están aplicados
    if [[ -f "$applied_marker" ]]; then
        if [[ "${SKIP_PATCH:-0}" == "1" ]]; then
            log "Parches ya aplicados (--skip-patch activo). Saltando Stage 2."
            return 0
        fi
        die "Los parches ya están aplicados ($applied_marker existe).
Usa --skip-patch para saltar, o --clean para revertir."
    fi

    # 1. Backup de los archivos que tocan los parches
    log "Creando backups en $backup_dir ..."
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        mkdir -p "$backup_dir"

        local files_to_backup=(
            "bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi"
            "bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi"
            "rootfs/boot/extlinux/extlinux.conf"
        )

        for f in "${files_to_backup[@]}"; do
            local src="$LDK_DIR/$f"
            local dst="$backup_dir/$f"
            if [[ -f "$src" ]]; then
                mkdir -p "$(dirname "$dst")"
                cp -p "$src" "$dst"
                log "  Backup: $f"
            else
                warn "  No encontrado para backup: $f"
            fi
        done

        # Verificación informativa: EEPROM bypass upstream (no es nuestro cambio)
        local mb2_bct="$LDK_DIR/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts"
        if [[ -f "$mb2_bct" ]]; then
            log "Verificando EEPROM bypass de upstream en $mb2_bct ..."
            if grep -q 'cvm_eeprom_read_size = <0x0>' "$mb2_bct" && \
               grep -q 'cvb_eeprom_read_size = <0x0>' "$mb2_bct"; then
                log "  OK: cvm_eeprom_read_size y cvb_eeprom_read_size = <0x0> (bypass activo)"
            else
                warn "  ADVERTENCIA: El bypass de EEPROM upstream puede haber cambiado en esta versión del BSP."
                warn "  Revisa $mb2_bct manualmente."
            fi
        fi
    else
        log "  [DRY-RUN] Se harían backups de archivos de pinmux y extlinux."
    fi

    # 2. Aplicar parches con quilt
    log "Aplicando parches con quilt ..."
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        (
            export QUILT_PATCHES="$VK_DIR/patches"
            export QUILT_SERIES="$VK_DIR/patches/series"
            cd "$LDK_DIR"
            quilt push -a
        )
    else
        log "  [DRY-RUN] Se ejecutaría: QUILT_PATCHES=$VK_DIR/patches quilt push -a"
    fi

    # 3. Validaciones post-parche
    log "Validando cambios post-parche ..."
    _validate_pinmux
    _validate_extlinux
    _validate_dtc_compile

    # 4. Marcar como aplicado
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        echo "applied_at=${BUILD_TS}" > "$applied_marker"
        echo "patches=$(cd "$VK_DIR/patches" && grep -v '^#' series | tr '\n' ',')" >> "$applied_marker"
        log "Marcador creado: $applied_marker"
    fi

    log "Stage 2 completado OK."
}

_validate_pinmux() {
    local dp_dtsi="$LDK_DIR/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi"
    local hdmi_dtsi="$LDK_DIR/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi"
    local errors=0

    for dtsi in "$dp_dtsi" "$hdmi_dtsi"; do
        local fname
        fname=$(basename "$dtsi")

        if [[ "${DRY_RUN:-0}" == "1" ]]; then
            log "  [DRY-RUN] Validaría pinmux en $fname"
            continue
        fi

        # Verificar gen2_i2c_scl_pcc7
        if grep -A6 'gen2_i2c_scl_pcc7' "$dtsi" | grep -q 'nvidia,function = "gp"' && \
           grep -A6 'gen2_i2c_scl_pcc7' "$dtsi" | grep -q 'nvidia,pull = <TEGRA_PIN_PULL_UP>'; then
            log "  OK: $fname — gen2_i2c_scl_pcc7 → gp + PULL_UP"
        else
            warn "  ERROR: $fname — gen2_i2c_scl_pcc7 no parcheado correctamente"
            (( errors++ )) || true
        fi

        # Verificar gen2_i2c_sda_pdd0
        if grep -A6 'gen2_i2c_sda_pdd0' "$dtsi" | grep -q 'nvidia,function = "gp"' && \
           grep -A6 'gen2_i2c_sda_pdd0' "$dtsi" | grep -q 'nvidia,pull = <TEGRA_PIN_PULL_UP>'; then
            log "  OK: $fname — gen2_i2c_sda_pdd0 → gp + PULL_UP"
        else
            warn "  ERROR: $fname — gen2_i2c_sda_pdd0 no parcheado correctamente"
            (( errors++ )) || true
        fi
    done

    [[ $errors -eq 0 ]] || die "Validación de pinmux fallida ($errors errores). Revisa los parches."
}

_validate_extlinux() {
    local extlinux="$LDK_DIR/rootfs/boot/extlinux/extlinux.conf"

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        log "  [DRY-RUN] Validaría root=/dev/sda1 rootwait en extlinux.conf"
        return
    fi

    if [[ ! -f "$extlinux" ]]; then
        warn "  No existe $extlinux — se validará tras apply_binaries.sh"
        return
    fi

    if grep -qE 'root=/dev/sda1.*rootwait' "$extlinux"; then
        log "  OK: extlinux.conf contiene root=/dev/sda1 rootwait"
    else
        warn "  ADVERTENCIA: extlinux.conf no contiene 'root=/dev/sda1 rootwait'"
        warn "  Verifica el parche 0003 o Stage 3."
    fi
}

_validate_dtc_compile() {
    if ! command -v dtc &>/dev/null; then
        warn "  dtc no disponible, saltando compilación de prueba."
        return
    fi

    if [[ "${DRY_RUN:-0}" == "1" ]]; then
        log "  [DRY-RUN] Compilaría los dtsi parcheados con dtc."
        return
    fi

    local dp_dtsi="$LDK_DIR/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi"
    log "  Compilando $dp_dtsi con dtc (prueba de sintaxis) ..."
    if dtc -I dts -O dtb -o /tmp/veronte_kai_test.dtb "$dp_dtsi" 2>/tmp/dtc_err.log; then
        log "  OK: dtc compiló sin errores."
        rm -f /tmp/veronte_kai_test.dtb
    else
        warn "  dtc reportó advertencias/errores (puede ser normal para .dtsi sin nodo raíz):"
        cat /tmp/dtc_err.log | head -10 | while read -r line; do warn "    $line"; done
    fi
    rm -f /tmp/dtc_err.log
}
