#!/usr/bin/env bash
# setup_http_boot.sh — Configura un servidor HTTP Boot en el host
# para que Veronte Kai arranque el kernel por Ethernet (L4TLauncher HTTP Boot)
#
# REQUISITOS en el host:
#   sudo apt install dnsmasq python3 iproute2
#
# USO:
#   sudo ./setup_http_boot.sh [interfaz_ethernet]   ej: sudo ./setup_http_boot.sh eth0
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LDK_DIR="$(cd "$VK_DIR/.." && pwd)/Linux_for_Tegra"
ROOTFS_DIR="$LDK_DIR/rootfs"

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; BLU='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GRN}[HTTP]${NC} $*"; }
warn()  { echo -e "${YEL}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${BLU}>>> $*${NC}"; }

[[ $EUID -eq 0 ]] || die "Necesita sudo. Usa: sudo $0 [interfaz]"

# ── Detectar interfaz Ethernet ───────────────────────────────────────────────
ETH_IFACE="${1:-}"
if [[ -z "$ETH_IFACE" ]]; then
    echo ""
    info "Interfaces disponibles:"
    ip -o link show | grep -v "lo\|docker\|veth\|br-" | awk -F': ' '{print "  " $2}'
    echo ""
    read -rp "Interfaz Ethernet conectada a Veronte Kai: " ETH_IFACE
fi
[[ -n "$ETH_IFACE" ]] || die "Interfaz no especificada"
ip link show "$ETH_IFACE" &>/dev/null || die "Interfaz $ETH_IFACE no existe"

# ── Detectar IP del host en esa interfaz ────────────────────────────────────
HOST_IP=$(ip -4 addr show "$ETH_IFACE" | grep -oP '(?<=inet )\d+\.\d+\.\d+\.\d+' | head -1 || true)
if [[ -z "$HOST_IP" ]]; then
    warn "La interfaz $ETH_IFACE no tiene IP. Asignando IP estática 192.168.100.1 ..."
    ip addr add 192.168.100.1/24 dev "$ETH_IFACE" 2>/dev/null || true
    ip link set "$ETH_IFACE" up
    HOST_IP="192.168.100.1"
    BOARD_IP="192.168.100.2"
    NETMASK="255.255.255.0"
    DHCP_RANGE="192.168.100.10,192.168.100.50,12h"
else
    # Usar misma subred
    NETWORK=$(echo "$HOST_IP" | cut -d. -f1-3)
    BOARD_IP="${NETWORK}.100"
    NETMASK="255.255.255.0"
    DHCP_RANGE="${NETWORK}.10,${NETWORK}.50,12h"
fi

HTTP_PORT=8080
SERVE_DIR="$VK_DIR/out/http_boot"

echo ""
echo "=========================================="
echo "  Veronte Kai — HTTP Boot Server"
echo "=========================================="
echo "  Host IP:   $HOST_IP (interfaz $ETH_IFACE)"
echo "  HTTP URL:  http://$HOST_IP:$HTTP_PORT/"
echo "  DHCP:      $DHCP_RANGE"
echo "  Files:     $SERVE_DIR"
echo "=========================================="

# ── Verificar dependencias ───────────────────────────────────────────────────
step "Verificando dependencias"
for cmd in dnsmasq python3; do
    command -v "$cmd" &>/dev/null || die "Falta: $cmd  →  sudo apt install $cmd"
done

# ── Preparar archivos del servidor HTTP ─────────────────────────────────────
step "Preparando archivos de boot"
mkdir -p "$SERVE_DIR/boot/extlinux"

# Kernel
KERNEL_SRC="$ROOTFS_DIR/boot/Image"
[[ -f "$KERNEL_SRC" ]] || die "Kernel no encontrado: $KERNEL_SRC"
info "Copiando kernel ($(du -sh "$KERNEL_SRC" | cut -f1)) ..."
cp -p "$KERNEL_SRC" "$SERVE_DIR/boot/Image"

# Initrd
INITRD_SRC="$ROOTFS_DIR/boot/initrd"
if [[ -f "$INITRD_SRC" ]]; then
    info "Copiando initrd ..."
    cp -p "$INITRD_SRC" "$SERVE_DIR/boot/initrd"
else
    warn "initrd no encontrado — bootará sin initrd"
fi

# DTB
DTB_SRC="$LDK_DIR/kernel/dtb/tegra234-p3768-0000+p3767-0003-nv.dtb"
[[ -f "$DTB_SRC" ]] || die "DTB no encontrado: $DTB_SRC"
info "Copiando DTB ..."
cp -p "$DTB_SRC" "$SERVE_DIR/boot/tegra234-p3768-0000+p3767-0003-nv.dtb"

# extlinux.conf — apunta a rootfs en /dev/sda1 (USB SD reader)
cat > "$SERVE_DIR/boot/extlinux/extlinux.conf" << EOF
TIMEOUT 30
DEFAULT veronte

MENU TITLE Veronte Kai — HTTP Boot

LABEL veronte
      MENU LABEL Veronte Kai kernel (rootfs en /dev/sda1)
      LINUX /boot/Image
      INITRD /boot/initrd
      FDT /boot/tegra234-p3768-0000+p3767-0003-nv.dtb
      APPEND console=ttyTCU0,115200 console=tty0 root=/dev/sda1 rootwait rw efi=runtime pci=pcie_bus_perf
EOF
info "extlinux.conf creado con root=/dev/sda1"

# ── Configurar dnsmasq para DHCP + HTTP Boot ────────────────────────────────
step "Configurando dnsmasq (DHCP + HTTP Boot)"

DNSMASQ_CONF="/tmp/veronte_dnsmasq_$$.conf"
cat > "$DNSMASQ_CONF" << EOF
# dnsmasq config para HTTP Boot — Veronte Kai
interface=$ETH_IFACE
bind-interfaces
dhcp-range=$DHCP_RANGE
dhcp-option=3,$HOST_IP         # gateway
dhcp-option=6,$HOST_IP         # DNS

# HTTP Boot option (RFC 5071 / UEFI spec)
# Opción 67: boot file name con URL HTTP
dhcp-option=67,http://$HOST_IP:$HTTP_PORT/boot/extlinux/extlinux.conf

# Para UEFI HTTP Boot (opción 60 class identifier)
dhcp-option=vendor:HTTPClient,60,"HTTPClient"

# Log
log-dhcp
EOF

# Parar dnsmasq existente si hay
systemctl stop dnsmasq 2>/dev/null || true
pkill dnsmasq 2>/dev/null || true
sleep 1

# Lanzar dnsmasq
info "Iniciando dnsmasq en $ETH_IFACE ..."
dnsmasq --conf-file="$DNSMASQ_CONF" --pid-file=/tmp/veronte_dnsmasq.pid \
        --log-facility=/tmp/veronte_dnsmasq.log &
DNSMASQ_PID=$!
sleep 1
kill -0 "$DNSMASQ_PID" 2>/dev/null || die "dnsmasq no arrancó — revisa /tmp/veronte_dnsmasq.log"
info "dnsmasq PID=$DNSMASQ_PID"

# ── Lanzar servidor HTTP ─────────────────────────────────────────────────────
step "Iniciando servidor HTTP en puerto $HTTP_PORT"

# Cambiar al directorio de servicio
cd "$SERVE_DIR"
info "Sirviendo desde: $SERVE_DIR"
info "URL base: http://$HOST_IP:$HTTP_PORT/"
info ""
info "Archivos disponibles:"
find . -type f | sort | while read -r f; do
    SIZE=$(du -sh "$f" 2>/dev/null | cut -f1)
    echo "    $SIZE  http://$HOST_IP:$HTTP_PORT/${f#./}"
done

echo ""
echo "=========================================="
echo -e "  ${GRN}Servidor HTTP listo${NC}"
echo "=========================================="
echo "  Ahora conecta la Veronte Kai por Ethernet"
echo "  y enciéndela (sin modo recovery)."
echo ""
echo "  El UEFI debería:"
echo "  1. Obtener IP por DHCP de este servidor"
echo "  2. Descargar el kernel via HTTP"
echo "  3. Arrancar Linux"
echo "  4. Linux montará /dev/sda1 (tu lector USB-SD)"
echo ""
echo "  Para parar: Ctrl+C"
echo "  Logs dnsmasq: tail -f /tmp/veronte_dnsmasq.log"
echo "=========================================="
echo ""

# Cleanup on exit
cleanup() {
    info "Parando servicios ..."
    kill "$DNSMASQ_PID" 2>/dev/null || true
    pkill dnsmasq 2>/dev/null || true
    rm -f "$DNSMASQ_CONF" /tmp/veronte_dnsmasq.pid
    info "Limpieza completada."
}
trap cleanup EXIT INT TERM

# Servidor HTTP (Python simple)
python3 -m http.server "$HTTP_PORT" --bind "$HOST_IP"
