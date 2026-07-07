#!/usr/bin/env bash
# Stage 4 — Generación del wrapper de flasheo
# Lee configs/board.env y genera scripts/flash_veronte_kai.sh + out/manifest.txt
# Llamado por build_veronte_kai.sh; NO ejecutar directamente.
set -euo pipefail
IFS=$'\n\t'

stage4_flash_wrapper() {
    log "=== Stage 4: Generando wrapper de flasheo ==="

    local board_env="$VK_DIR/configs/board.env"
    local flash_script="$VK_DIR/scripts/flash_veronte_kai.sh"
    local manifest="$VK_DIR/out/manifest.txt"

    # Cargar board.env
    [[ -f "$board_env" ]] || die "No se encuentra $board_env"
    # shellcheck source=/dev/null
    source "$board_env"

    log "  BOARDID=$BOARDID  BOARDSKU=$BOARDSKU  FAB=$FAB  BOARDREV=$BOARDREV"
    log "  BOARD_CONF=$BOARD_CONF  FLASH_TARGET=$FLASH_TARGET"

    # Generar flash_veronte_kai.sh
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        cat > "$flash_script" << FLASH_EOF
#!/usr/bin/env bash
# AUTO-GENERADO por build_veronte_kai.sh el ${BUILD_TS} — NO EDITAR A MANO
# Para cambios, edita configs/board.env y regenera con Stage 4.
set -euo pipefail
IFS=\$'\\n\\t'

SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
LDK_DIR="\$(cd "\$SCRIPT_DIR/../.." && pwd)/Linux_for_Tegra"

echo "=========================================="
echo "  Veronte Kai — Flash Script"
echo "=========================================="
echo "  BOARDID   : ${BOARDID}"
echo "  BOARDSKU  : ${BOARDSKU}"
echo "  FAB       : ${FAB}"
echo "  BOARDREV  : ${BOARDREV}"
echo "  CONF      : ${BOARD_CONF}.conf"
echo "  TARGET    : ${FLASH_TARGET}"
echo "  LDK_DIR   : \$LDK_DIR"
echo "=========================================="
echo ""
echo "ADVERTENCIA: Este script flasheará el módulo Jetson conectado."
echo "Asegúrate de que:"
echo "  1. El módulo P3767-0003 está en modo RECOVERY (mantén REC durante reset)."
echo "  2. El cable USB-C está conectado al host."
echo "  3. NO hay ningún otro módulo Jetson conectado al host."
echo ""
read -rp "¿Continuar con el flasheo? [s/N] " confirm
if [[ "\$confirm" != "s" && "\$confirm" != "S" ]]; then
    echo "Flasheo cancelado."
    exit 0
fi

[[ -f "\$LDK_DIR/flash.sh" ]] || { echo "ERROR: No se encuentra \$LDK_DIR/flash.sh"; exit 1; }
[[ -f "\$LDK_DIR/${BOARD_CONF}.conf" ]] || { echo "ERROR: No se encuentra \$LDK_DIR/${BOARD_CONF}.conf — ¿se aplicaron los parches (Stage 2)?"; exit 1; }

echo "Iniciando flasheo..."
cd "\$LDK_DIR"
sudo BOARDID=${BOARDID} BOARDSKU=${BOARDSKU} FAB=${FAB} BOARDREV=${BOARDREV} FORCE_ACCESS=1 \\
     ./flash.sh ${BOARD_CONF} ${FLASH_TARGET} "\$@"
FLASH_EOF

        chmod 0755 "$flash_script"
        log "  Generado: $flash_script (chmod 0755)"
    else
        log "  [DRY-RUN] Se generaría: $flash_script"
    fi

    # Generar manifest.txt con SHA256 de artefactos clave
    log "Calculando SHA256 de artefactos ..."
    mkdir -p "$VK_DIR/out"

    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        {
            echo "# Veronte Kai Build Manifest"
            echo "# Generado: ${BUILD_TS}"
            echo ""

            local manifest_files=(
                "$VK_DIR/configs/$BOARD_CONF.conf:configs/$BOARD_CONF.conf"
                "$LDK_DIR/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi:Linux_for_Tegra/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi"
                "$LDK_DIR/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi:Linux_for_Tegra/bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-hdmi-a03.dtsi"
                "$LDK_DIR/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts:Linux_for_Tegra/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts"
                "$flash_script:scripts/flash_veronte_kai.sh"
            )

            for entry in "${manifest_files[@]}"; do
                local fpath="${entry%%:*}"
                local label="${entry##*:}"
                if [[ -f "$fpath" ]]; then
                    local sha
                    sha=$(sha256sum "$fpath" | awk '{print $1}')
                    echo "$sha  $label"
                    log "  SHA256 $label: ${sha:0:12}..."
                else
                    echo "MISSING  $label"
                    warn "  Archivo no encontrado para manifest: $fpath"
                fi
            done
        } > "$manifest"

        log "  Manifest guardado: $manifest"
    else
        log "  [DRY-RUN] Se calcularían SHA256 y se generaría $manifest"
    fi

    # Instrucciones finales
    echo ""
    echo "=========================================="
    echo "  Build completado — Instrucciones de flasheo"
    echo "=========================================="
    echo "  1. Pon el módulo en modo RECOVERY:"
    echo "     Mantén presionado el botón REC y pulsa RESET (o power on)."
    echo "  2. Conecta el cable USB-C Recovery al host."
    echo "  3. Verifica que el módulo se enumera:"
    echo "     lsusb | grep -i nvidia   # Debe mostrar 0955:7523"
    echo "  4. Ejecuta el flasheo:"
    if [[ "${DRY_RUN:-0}" == "0" ]]; then
        echo "     $flash_script"
    else
        echo "     [DRY-RUN] $flash_script  (no generado)"
    fi
    echo "=========================================="

    log "Stage 4 completado OK."
}
