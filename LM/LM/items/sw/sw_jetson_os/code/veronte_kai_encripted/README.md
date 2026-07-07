# Para generar la SD

cd /home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra

sudo ./tools/l4t_create_default_user.sh \
  -u nvidia \
  -p 'TU_PASSWORD' \
  -n jetson-orin \
  -a \
  --accept-license

cd /home/ejn3@ad.embention.com/Documents/Jetson/veronte_kai_encripted
cp ~/.ssh/jetson_orin_nvidia.pub ./authorized_keys.pub
sudo -E ./apply_hardening_to_l4t.sh

cd /home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra/tools

sudo ROOTFS_DIR="$(realpath ../rootfs)" ./jetson-disk-image-creator.sh \
  -o ../orin-nano-r36.5-super-hardened-sd.img \
  -b jetson-orin-nano-devkit-super \
  -d SD

DEV=/dev/sdb

lsblk -p -o NAME,TYPE,SIZE,FSTYPE,LABEL,MODEL,MOUNTPOINTS "$DEV"

for p in $(lsblk -lnpo NAME "$DEV" | tail -n +2); do
    sudo umount "$p" 2>/dev/null || true
    sudo udisksctl unmount -b "$p" 2>/dev/null || true
done

sudo dd \
  if=/home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra/orin-nano-r36.5-super-hardened-sd.img \
  of="$DEV" \
  bs=16M \
  status=progress \
  conv=fsync

sync
sudo eject "$DEV"


# Generar bien
1. Generar claves finales
export L4T=/home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra
export HARD=/home/ejn3@ad.embention.com/Documents/Jetson/veronte_kai_encripted
export KEYDIR=$HARD/keys
export PKC=$HARD/secureboot_keys/rsa3k.pem

cd "$KEYDIR"

openssl rand -hex 32 | tr -d '\n' > oem_k1.key
openssl rand -hex 32 | tr -d '\n' > sym_t234.key
openssl rand -hex 16 | tr -d '\n' > sym2_t234.key
openssl rand -hex 16 | tr -d '\n' > auth_t234.key

chmod 600 *.key

wc -c *.key

Tiene que salir:

32 auth_t234.key
64 oem_k1.key
32 sym2_t234.key
64 sym_t234.key
192 total
2. Regenerar EKS final
cd "$KEYDIR"
source .venv/bin/activate 2>/dev/null || true

python /home/ejn3@ad.embention.com/Documents/Jetson/public_sources_r36.5.0/Linux_for_Tegra/source/jetson-optee-srcs/optee/samples/hwkey-agent/host/tool/gen_ekb/gen_ekb.py \
  -chip t234 \
  -oem_k1_key oem_k1.key \
  -in_sym_key sym_t234.key \
  -in_sym_key2 sym2_t234.key \
  -in_auth_key auth_t234.key \
  -out eks_t234.img

Copia al BSP:

sudo cp "$KEYDIR/eks_t234.img" "$L4T/bootloader/eks_t234.img"
sudo cp "$KEYDIR/sym2_t234.key" "$L4T/disk_enc.key"
sudo cp "$KEYDIR/sym_t234.key" "$L4T/user_encryption.key"

sudo chmod 600 "$L4T/disk_enc.key" "$L4T/user_encryption.key"

Checks:

cd "$L4T"

sudo diff disk_enc.key "$KEYDIR/sym2_t234.key" && echo "OK: disk_enc.key == sym2_t234.key"
sudo diff user_encryption.key "$KEYDIR/sym_t234.key" && echo "OK: user_encryption.key == sym_t234.key"
cmp -s bootloader/eks_t234.img "$KEYDIR/eks_t234.img" && echo "OK: eks_t234.img copied"
3. Crear XML de fuses con PKC + OEM_K1

Tu XML actual solo tiene PublicKeyHash, BootSecurityInfo=0x1 y SecurityMode=0x1. Para añadir OEM_K1, hay que meter el fuse OemK1.

NVIDIA muestra RSA-3K con BootSecurityInfo=0x1, y también muestra OemK1 con BootSecurityInfo=0x200; para combinar RSA-3K + OEM_K1 usamos el OR de flags: 0x1 | 0x200 = 0x201.

HASH=$(grep -o '0x[0-9a-fA-F]\{128\}' "$HARD/secureboot_keys/fuse_rsa3k.xml" | head -n 1)
OEMK1="0x$(cat "$KEYDIR/oem_k1.key")"

echo "$HASH"
echo "$OEMK1"

cat > "$HARD/secureboot_keys/fuse_rsa3k_oemk1.xml" <<EOF
<genericfuse MagicId="0x45535546" version="1.0.0">
    <fuse name="PublicKeyHash" size="64" value="$HASH"/>
    <fuse name="OemK1" size="32" value="$OEMK1"/>
    <fuse name="BootSecurityInfo" size="4" value="0x201"/>
    <fuse name="SecurityMode" size="4" value="0x1"/>
</genericfuse>
EOF

cat "$HARD/secureboot_keys/fuse_rsa3k_oemk1.xml"
4. Test de fuses final

Con la Jetson en Force Recovery:

cd "$L4T"

sudo ./odmfuse.sh \
  --test \
  -X "$HARD/secureboot_keys/fuse_rsa3k_oemk1.xml" \
  -i 0x23 \
  jetson-orin-nano-devkit-super

Si acaba en Finish, el test está bien.

5. Importante: antes de quemar

Guarda en KeePass/offline, mínimo:

rsa3k.pem
fuse_rsa3k_oemk1.xml
oem_k1.key
sym_t234.key
sym2_t234.key
auth_t234.key
eks_t234.img
disk_enc.key
user_encryption.key
PK.key / KEK.key / db_1.key
uefi_keys.conf

Si pierdes rsa3k.pem, no podrás generar imágenes que arranquen después de quemar PKC fuses. Si pierdes oem_k1.key, no podrás regenerar un EKS compatible con esa placa.

6. Quemar fuses reales

Solo cuando estés listo:

cd "$L4T"

sudo ./odmfuse.sh \
  -X "$HARD/secureboot_keys/fuse_rsa3k_oemk1.xml" \
  -i 0x23 \
  jetson-orin-nano-devkit-super

Después de esto, la imagen anterior con oem_k1=0000... ya no debería servir. Tienes que flashear con el EKS generado con el oem_k1.key real.

7. Reflasheo final después de quemar

Usas el mismo flujo que ya te funcionó:

cd "$HARD"

PUBKEYS_FILE="$HARD/authorized_keys.pub" \
L4T_DIR="$L4T" \
ROOTFS="$L4T/rootfs" \
USER_NAME="nvidia" \
HOSTNAME="EMB00829-ejn3" \
IFACE="enP8p1s0" \
IP_CIDR="192.168.3.31/22" \
GATEWAY="192.168.0.1" \
DNS="1.1.1.1;8.8.8.8;" \
TIMEZONE="Europe/Madrid" \
sudo -E ./apply_hardening_to_l4t.sh
cd "$L4T"

sudo rm -rf tools/kernel_flash/images tools/kernel_flash/temp_initrdflash
sudo rm -rf bootloader/signed bootloader/enc_signed
sudo rm -f bootloader/user_data_encrypted.img_ext bootloader/system_root_encrypted.img_ext
sudo rm -f bootloader/flashcmd.txt bootloader/flash.xml* bootloader/secureflash.xml

sudo mkdir -p tools/kernel_flash/images/internal tools/kernel_flash/images/external
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --network usb0 \
  --showlogs \
  -u "$PKC" \
  --uefi-keys "$HARD/uefi_keys/uefi_keys.conf" \
  --uefi-enc ./user_encryption.key \
  -p "-c bootloader/generic/cfg/flash_t234_qspi.xml" \
  --no-flash \
  jetson-orin-nano-devkit-super internal
sudo ROOTFS_ENC=1 ./tools/kernel_flash/l4t_initrd_flash.sh \
  --network usb0 \
  --showlogs \
  --no-flash \
  --external-device mmcblk0p1 \
  -S 50GiB \
  -c ./tools/kernel_flash/flash_l4t_t234_nvme_rootfs_enc.xml \
  --external-only \
  --append \
  -u "$PKC" \
  --uefi-keys "$HARD/uefi_keys/uefi_keys.conf" \
  --uefi-enc ./user_encryption.key \
  -i ./disk_enc.key \
  jetson-orin-nano-devkit-super external
sudo ./tools/kernel_flash/l4t_initrd_flash.sh \
  --network usb0 \
  --showlogs \
  --flash-only