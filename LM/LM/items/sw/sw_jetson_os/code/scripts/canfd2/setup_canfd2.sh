#!/bin/bash
# =============================================================================
#  setup_canfd2.sh  –  Configura CAN FD 2 Click (TLE9255W) en Jetson Nano
# =============================================================================
#
#  Qué hace este script:
#    1. Habilita el bus SPI1 si no está activo
#    2. Instala spidev para Python si falta
#    3. Llama a canfd2_init.py para poner el TLE9255W en modo Normal
#    4. Carga los módulos del kernel CAN
#    5. Configura y levanta la interfaz can0 con el bitrate indicado
#
#  Conexiones físicas (Jetson Nano 40-pin → CAN FD 2 Click MikroBUS):
#
#    ┌──────────────────────┬─────────────┬──────────────────────┐
#    │  Jetson Nano Pin     │  Función    │  CAN FD 2 Click      │
#    ├──────────────────────┼─────────────┼──────────────────────┤
#    │  Pin 19 (SPI1_MOSI)  │  MOSI       │  MOSI                │
#    │  Pin 21 (SPI1_MISO)  │  MISO       │  MISO                │
#    │  Pin 23 (SPI1_SCK)   │  SCK        │  SCK                 │
#    │  Pin 24 (SPI1_CS0#)  │  CS         │  CS                  │
#    │  Pin 29 (CAN0_TX)    │  CAN TX     │  TX                  │
#    │  Pin 31 (CAN0_RX)    │  CAN RX     │  RX                  │
#    │  Pin  1 (3.3V)       │  VIO        │  3.3V                │
#    │  Pin  2 (5V)         │  VCC/VBAT   │  5V                  │
#    │  Pin  6 (GND)        │  GND        │  GND                 │
#    └──────────────────────┴─────────────┴──────────────────────┘
#
#    CAN_H y CAN_L salen del conector verde del CAN FD 2 Click.
#
#  Uso:
#    sudo bash setup_canfd2.sh                     # bitrate 500 kbps por defecto
#    sudo bash setup_canfd2.sh 1000000             # 1 Mbps
#    sudo bash setup_canfd2.sh 250000 can1         # 250 kbps en interfaz can1
#
#  Nota: Para que el CAN del Jetson Nano funcione, activa el overlay de CAN en
#    /boot/extlinux/extlinux.conf  añadiendo:
#      FDT_OVERLAYS /boot/tegra210-p3448-0000-p3449-0000-a02-overlay.dtb
#    O bien usa el Jetson-IO:  sudo /opt/nvidia/jetson-io/jetson-io.py
# =============================================================================

set -e

# ──────────────────────────────────────────────────────────────────────────────
#  Parámetros
# ──────────────────────────────────────────────────────────────────────────────
BITRATE="${1:-1000000}"          # bitrate CAN (default 1 Mkbps)
CAN_IFACE="${2:-can0}"          # interfaz CAN de Linux
SPI_BUS=0                       # spidev0.x  → SPI1 Jetson Nano
SPI_DEV=0                       # spidev x.0 → CS0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="/usr/local/sbin/canfd2_init.py"

# ──────────────────────────────────────────────────────────────────────────────
#  Colores
# ──────────────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[!!]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC}  $*"; exit 1; }
section() { echo -e "\n${YELLOW}──── $* ────${NC}"; }

# ──────────────────────────────────────────────────────────────────────────────
#  Verificar root
# ──────────────────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Ejecuta como root: sudo bash $0"

echo ""
echo "  CAN FD 2 Click (TLE9255W) – Setup para Jetson Nano"
echo "  Bitrate: ${BITRATE} bps    Interfaz: ${CAN_IFACE}"
echo ""

# ──────────────────────────────────────────────────────────────────────────────
#  1. Verificar / habilitar SPI
# ──────────────────────────────────────────────────────────────────────────────
section "1. SPI"

SPI_DEV_PATH="/dev/spidev${SPI_BUS}.${SPI_DEV}"

if [[ ! -e "${SPI_DEV_PATH}" ]]; then
    warn "${SPI_DEV_PATH} no existe. Intentando cargar spidev..."
    modprobe spidev 2>/dev/null || true
    sleep 1
fi

if [[ ! -e "${SPI_DEV_PATH}" ]]; then
    warn "SPI no habilitado. Para habilitarlo en Jetson Nano:"
    echo ""
    echo "  Opción A (Jetson-IO GUI):"
    echo "    sudo /opt/nvidia/jetson-io/jetson-io.py"
    echo "    → Configure Jetson Nano CSI Connector → SPI1"
    echo ""
    echo "  Opción B (manual) – añadir en /boot/extlinux/extlinux.conf:"
    echo "    FDT_OVERLAYS /boot/tegra210-p3448-0000-p3449-0000-a02-overlay.dtb"
    echo ""
    error "Habilita SPI y vuelve a ejecutar este script."
fi

info "${SPI_DEV_PATH} disponible"

# ──────────────────────────────────────────────────────────────────────────────
#  2. Dependencias Python
# ──────────────────────────────────────────────────────────────────────────────
section "2. Dependencias Python"

if ! python3 -c "import spidev" 2>/dev/null; then
    info "Instalando spidev..."
    if python3 -m pip install spidev --quiet 2>/dev/null; then
        info "spidev instalado via pip"
    elif apt-get install -y python3-spidev -qq 2>/dev/null; then
        info "spidev instalado via apt"
    else
        warn "No se pudo instalar spidev automáticamente. Instálalo manualmente:"
        echo "    sudo apt-get install python3-spidev"
        echo "  o bien:"
        echo "    sudo apt-get install python3-pip && pip3 install spidev"
        exit 1
    fi
fi
info "spidev disponible"

# ──────────────────────────────────────────────────────────────────────────────
#  3. Inicializar TLE9255W via SPI
# ──────────────────────────────────────────────────────────────────────────────
section "3. Configuración del transceiver TLE9255W (SPI)"

[[ ! -f "${PYTHON_SCRIPT}" ]] && error "No se encontró ${PYTHON_SCRIPT}"

python3 "${PYTHON_SCRIPT}" --bus "${SPI_BUS}" --device "${SPI_DEV}" --verify
info "Transceiver configurado en modo Normal Operation"

# ──────────────────────────────────────────────────────────────────────────────
#  4. Módulos del kernel CAN
# ──────────────────────────────────────────────────────────────────────────────
section "4. Módulos del kernel CAN"

for mod in can can_dev mttcan; do
    if ! lsmod | grep -q "^${mod} "; then
        if modprobe "${mod}" 2>/dev/null; then
            info "Módulo ${mod} cargado"
        else
            warn "No se pudo cargar ${mod} (puede que no sea necesario en tu kernel)"
        fi
    else
        info "Módulo ${mod} ya cargado"
    fi
done

# ──────────────────────────────────────────────────────────────────────────────
#  5. Configurar interfaz CAN
# ──────────────────────────────────────────────────────────────────────────────
section "5. Interfaz CAN: ${CAN_IFACE}"

if ! ip link show "${CAN_IFACE}" &>/dev/null; then
    error "Interfaz ${CAN_IFACE} no encontrada. Verifica el device tree overlay de CAN."
fi

# Bajar la interfaz si estaba activa
if ip link show "${CAN_IFACE}" | grep -q "UP"; then
    ip link set "${CAN_IFACE}" down
    info "Interfaz ${CAN_IFACE} bajada para reconfigurar"
fi

# Configurar bitrate y levantar
ip link set "${CAN_IFACE}" type can bitrate "${BITRATE}" restart-ms 100
ip link set "${CAN_IFACE}" up

info "Interfaz ${CAN_IFACE} levantada a ${BITRATE} bps"

# ──────────────────────────────────────────────────────────────────────────────
#  6. Verificación final
# ──────────────────────────────────────────────────────────────────────────────
section "6. Estado final"

ip -details -statistics link show "${CAN_IFACE}"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  CAN FD 2 Click listo para usar                  ${NC}"
echo -e "${GREEN}  Bus: ${CAN_IFACE}   Bitrate: ${BITRATE} bps               ${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo "  Prueba de recepción:   candump ${CAN_IFACE}"
echo "  Prueba de envío:       cansend ${CAN_IFACE} 123#DEADBEEF"
echo ""
