#!/bin/bash

# Le pasamos el dispositivo como argumento para no liar pifias (ej: ./format_hil.sh /dev/sdb)
SD_DEVICE=$1

if [ -z "$SD_DEVICE" ]; then
    echo "Error: Debes indicar la ruta de la tarjeta SD."
    echo "Uso: $0 /dev/sdX  (Usa el comando 'lsblk' para saber qué letra es tu tarjeta)"
    exit 1
fi

if [ ! -b "$SD_DEVICE" ]; then
    echo "Error: El dispositivo $SD_DEVICE no existe."
    exit 1
fi

echo "=========================================="
echo " PREPARANDO TARJETA PARA PROYECTO HIL"
echo "=========================================="

# 1. Desmontar todo por si acaso
echo "[1/4] Desmontando particiones en $SD_DEVICE..."
for partition in $(lsblk -ln -o MOUNTPOINT "$SD_DEVICE" | grep -v '^$'); do
    sudo umount "$partition"
    echo " -> $partition desmontada."
done

# 2. Borrado extremo de particiones
echo "[2/4] Destruyendo tabla de particiones vieja..."
sudo sfdisk --delete "$SD_DEVICE" > /dev/null 2>&1
sleep 1

# 3. Crear 1 sola partición FAT32 (Usando el 100% del espacio)
echo "[3/4] Creando nueva partición maestra (FAT32)..."
sudo parted -s "$SD_DEVICE" mklabel msdos
sudo parted -s "$SD_DEVICE" mkpart primary fat32 1MiB 100%

# Esperamos a que el sistema operativo detecte la nueva partición
sleep 2
PARTITION="${SD_DEVICE}1"

# 4. Darle formato
echo "[4/4] Formateando $PARTITION..."
sudo mkfs.fat -F 32 "$PARTITION" > /dev/null

echo "=========================================="
echo " ¡ÉXITO! Tu tarjeta está lista."
echo " Ahora solo tienes que montar $PARTITION y copiar tu BOOT.BIN, image.ub y tu ejecutable."
echo "=========================================="