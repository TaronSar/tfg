#!/usr/bin/env bash
# prepare_sdcard.sh — Copia el rootfs de Veronte Kai a una SD card (via USB reader)
# USO: sudo ./prepare_sdcard.sh [/dev/sdX]
# Si no se pasa dispositivo, muestra los disponibles y pide confirmación.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LDK_DIR="$(cd "$VK_DIR/.." && pwd)/Linux_for_Tegra"
ROOTFS_DIR="$LDK_DIR/rootfs"
DTB_SRC="$LDK_DIR/kernel/dtb/tegra234-p3768-0000+p3767-0003-nv.dtb"

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; NC='\033[0m'
info()  { echo -e "${GRN}[SD]${NC} $*"; }
warn()  { echo -e "${YEL}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Este script necesita sudo. Usa: sudo $0 [/dev/sdX]"

echo "=========================================="
echo "  Veronte Kai — Preparar SD Card"
echo "=========================================="
echo "  ROOTFS: $ROOTFS_DIR"
echo "  DTB:    $DTB_SRC"
echo "=========================================="

# --- Validar rootfs ---
[[ -f "$ROOTFS_DIR/usr/bin/bash" ]] || die "Rootfs incompleto: $ROOTFS_DIR"
[[ -f "$ROOTFS_DIR/boot/Image" ]]   || die "Kernel no encontrado en $ROOTFS_DIR/boot/Image"
[[ -f "$DTB_SRC" ]]                  || die "DTB no encontrado: $DTB_SRC"

# --- Seleccionar dispositivo ---
DEVICE="${1:-}"

if [[ -z "$DEVICE" ]]; then
    echo ""
    info "Dispositivos de bloque disponibles (excluye el disco del host):"
    lsblk -d -o NAME,SIZE,MODEL,TRAN | grep -v "^loop\|^sr" | head -20
    echo ""
    read -rp "Introduce el dispositivo SD card (ej: /dev/sdb, /dev/sdc): " DEVICE
fi

# Sanity checks
[[ -b "$DEVICE" ]] || die "Dispositivo no encontrado: $DEVICE"
[[ "$DEVICE" != "/dev/sda" ]] || die "No puedes usar /dev/sda — es el disco del host."
[[ "$DEVICE" =~ ^/dev/sd[b-z]$ ]] || { warn "Dispositivo inusual: $DEVICE"; }

DEVICE_SIZE_GB=$(lsblk -d -o SIZE --noheadings "$DEVICE" | tr -d ' \n' | sed 's/G//')
info "Dispositivo: $DEVICE  (tamaño: $(lsblk -d -o SIZE --noheadings "$DEVICE"))"
info "Modelo: $(lsblk -d -o MODEL --noheadings "$DEVICE" | xargs)"

echo ""
echo -e "${RED}ADVERTENCIA: Se borrará TODO el contenido de $DEVICE${NC}"
echo "¿Continuar? [escribir 'si' para confirmar]"
read -r confirm
[[ "$confirm" == "si" ]] || { info "Cancelado."; exit 0; }

# --- Desmontar particiones existentes ---
info "Desmontando particiones de $DEVICE ..."
umount "${DEVICE}"?* 2>/dev/null || true
sleep 1

# --- Particionar: GPT con una sola partición ext4 (toda la tarjeta) ---
info "Creando tabla de particiones GPT en $DEVICE ..."
parted -s "$DEVICE" mklabel gpt
parted -s "$DEVICE" mkpart primary ext4 0% 100%
sleep 2
partprobe "$DEVICE" 2>/dev/null || true
sleep 2

PARTITION="${DEVICE}1"
# Algunos lectores USB crean /dev/sdbp1 en vez de /dev/sdb1
[[ -b "$PARTITION" ]] || PARTITION="${DEVICE}p1"
[[ -b "$PARTITION" ]] || die "No se encontró partición: ${DEVICE}1 ni ${DEVICE}p1"

info "Formateando $PARTITION como ext4 ..."
mkfs.ext4 -L "APP" -F "$PARTITION"

# --- Montar y copiar rootfs ---
MNTPOINT="/mnt/veronte_sdcard_$$"
mkdir -p "$MNTPOINT"
trap "umount $MNTPOINT 2>/dev/null; rmdir $MNTPOINT 2>/dev/null" EXIT

info "Montando $PARTITION en $MNTPOINT ..."
mount "$PARTITION" "$MNTPOINT"

info "Copiando rootfs (esto puede tardar varios minutos) ..."
ROOTFS_SIZE=$(du -sh "$ROOTFS_DIR" 2>/dev/null | cut -f1)
info "  Tamaño aproximado del rootfs: $ROOTFS_SIZE"
rsync -aAXH --info=progress2 \
    --exclude='/proc/*' \
    --exclude='/sys/*' \
    --exclude='/dev/*' \
    --exclude='/run/*' \
    --exclude='/tmp/*' \
    "$ROOTFS_DIR/" "$MNTPOINT/"

# --- Copiar DTB correcto ---
info "Copiando DTB p3767-0003 a /boot/ ..."
cp -v "$DTB_SRC" "$MNTPOINT/boot/tegra234-p3768-0000+p3767-0003-nv.dtb"

# Copiar también los DTBOs necesarios para p3767-0003
DTB_DIR="$LDK_DIR/kernel/dtb"
for dtbo in \
    tegra234-p3768-0000+p3767-0000-dynamic.dtbo \
    tegra234-p3737-0000+p3701-0000-as-p3767-0003.dtbo; do
    [[ -f "$DTB_DIR/$dtbo" ]] && cp -v "$DTB_DIR/$dtbo" "$MNTPOINT/boot/" || warn "DTBO no encontrado: $dtbo (no crítico)"
done

# --- Verificar extlinux.conf ---
EXTLINUX="$MNTPOINT/boot/extlinux/extlinux.conf"
if [[ -f "$EXTLINUX" ]]; then
    info "extlinux.conf actual:"
    cat "$EXTLINUX"
    if ! grep -q "root=/dev/sda1" "$EXTLINUX"; then
        warn "extlinux.conf no tiene root=/dev/sda1 — corrigiendo ..."
        sed -i 's|APPEND.*|APPEND ${cbootargs} root=/dev/sda1 rootwait rw|' "$EXTLINUX"
        info "extlinux.conf actualizado."
    fi
else
    warn "No existe extlinux.conf — creando uno mínimo ..."
    mkdir -p "$MNTPOINT/boot/extlinux"
    cat > "$EXTLINUX" << 'EOF'
TIMEOUT 30
DEFAULT primary

MENU TITLE L4T boot options

LABEL primary
      MENU LABEL Veronte Kai primary kernel
      LINUX /boot/Image
      INITRD /boot/initrd
      APPEND ${cbootargs} root=/dev/sda1 rootwait rw
EOF
    info "extlinux.conf creado."
fi

# --- Crear directorios necesarios ---
for d in proc sys dev dev/pts run tmp; do
    mkdir -p "$MNTPOINT/$d"
done

# --- Resumen final ---
info "Sincronizando escrituras ..."
sync

USED=$(df -h "$MNTPOINT" | tail -1 | awk '{print $3}')
FREE=$(df -h "$MNTPOINT" | tail -1 | awk '{print $4}')
info "Espacio usado: $USED  |  Libre: $FREE"

echo ""
echo "=========================================="
echo "  SD Card preparada correctamente"
echo "=========================================="
echo "  Dispositivo: $DEVICE  →  $PARTITION"
echo "  Rootfs:      Ubuntu 22.04 + kernel L4T R36.5"
echo "  extlinux:    root=/dev/sda1 rootwait rw"
echo ""
echo "  Pasos siguientes:"
echo "  1. Retira la SD card del host"
echo "  2. Insértala en el lector USB"
echo "  3. Conecta el lector USB2.0 a la Veronte Kai"
echo "  4. Enciende la Veronte Kai (sin modo recovery)"
echo ""
echo "  Si UEFI no ve el USB, consulta el README:"
echo "  $VK_DIR/docs/usb_boot_troubleshooting.md"
echo "=========================================="
