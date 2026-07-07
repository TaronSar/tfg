#!/usr/bin/env bash
set -euo pipefail

L4T_DIR="${L4T_DIR:-/home/ejn3@ad.embention.com/Documents/Jetson/Linux_for_Tegra_og/Linux_for_Tegra}"
ROOTFS="${ROOTFS:-$L4T_DIR/rootfs}"

USER_NAME="${USER_NAME:-nvidia}"
HOSTNAME="${HOSTNAME:-jetson-orin}"

IFACE="${IFACE:-enP8p1s0}"
IP_CIDR="${IP_CIDR:-192.168.3.31/22}"
GATEWAY="${GATEWAY:-192.168.0.1}"
DNS="${DNS:-1.1.1.1;8.8.8.8;}"
TIMEZONE="${TIMEZONE:-Europe/Madrid}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBKEYS_FILE="${PUBKEYS_FILE:-$SCRIPT_DIR/authorized_keys.pub}"

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run with sudo:"
    echo "  sudo -E $0"
    exit 1
fi

if [ ! -d "$ROOTFS/etc" ]; then
    echo "ERROR: rootfs not found at: $ROOTFS"
    exit 1
fi

if [ ! -f "$PUBKEYS_FILE" ]; then
    echo "ERROR: public keys file not found: $PUBKEYS_FILE"
    exit 1
fi

if ! grep -q "^${USER_NAME}:" "$ROOTFS/etc/passwd"; then
    echo "ERROR: user '$USER_NAME' does not exist in rootfs."
    echo "Run this first:"
    echo "  cd $L4T_DIR"
    echo "  sudo ./tools/l4t_create_default_user.sh -u $USER_NAME -p 'PASSWORD' -n $HOSTNAME -a --accept-license"
    exit 1
fi

echo "[1/9] Hostname"
echo "$HOSTNAME" > "$ROOTFS/etc/hostname"

if grep -q '^127\.0\.1\.1' "$ROOTFS/etc/hosts"; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1 $HOSTNAME/" "$ROOTFS/etc/hosts"
else
    echo "127.0.1.1 $HOSTNAME" >> "$ROOTFS/etc/hosts"
fi

echo "[2/9] Timezone"
ln -sf "/usr/share/zoneinfo/$TIMEZONE" "$ROOTFS/etc/localtime"
echo "$TIMEZONE" > "$ROOTFS/etc/timezone"

echo "[3/9] Static Ethernet config"
install -d -m 755 "$ROOTFS/etc/NetworkManager/system-connections"

cat > "$ROOTFS/etc/NetworkManager/system-connections/wired-static.nmconnection" <<EOF
[connection]
id=wired-static
type=ethernet
interface-name=$IFACE
autoconnect=true

[ipv4]
method=manual
address1=$IP_CIDR,$GATEWAY
dns=$DNS

[ipv6]
method=ignore
EOF

chmod 600 "$ROOTFS/etc/NetworkManager/system-connections/wired-static.nmconnection"
chown root:root "$ROOTFS/etc/NetworkManager/system-connections/wired-static.nmconnection"

echo "[4/9] SSH key-only access"
USER_UID="$(awk -F: -v u="$USER_NAME" '$1==u {print $3}' "$ROOTFS/etc/passwd")"
USER_GID="$(awk -F: -v u="$USER_NAME" '$1==u {print $4}' "$ROOTFS/etc/passwd")"
USER_HOME="$(awk -F: -v u="$USER_NAME" '$1==u {print $6}' "$ROOTFS/etc/passwd")"

install -d -m 700 "$ROOTFS$USER_HOME/.ssh"
cat "$PUBKEYS_FILE" > "$ROOTFS$USER_HOME/.ssh/authorized_keys"
chmod 600 "$ROOTFS$USER_HOME/.ssh/authorized_keys"
chown -R "$USER_UID:$USER_GID" "$ROOTFS$USER_HOME/.ssh"

install -d -m 755 "$ROOTFS/etc/ssh/sshd_config.d"

cat > "$ROOTFS/etc/ssh/sshd_config.d/99-key-only.conf" <<EOF
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin no
PermitEmptyPasswords no
X11Forwarding no
AllowUsers $USER_NAME
EOF

chmod 644 "$ROOTFS/etc/ssh/sshd_config.d/99-key-only.conf"

echo "[5/9] Disable GUI, local TTY and serial gettys"
systemctl --root="$ROOTFS" set-default multi-user.target || true

systemctl --root="$ROOTFS" disable gdm.service gdm3.service display-manager.service lightdm.service sddm.service 2>/dev/null || true
systemctl --root="$ROOTFS" mask gdm.service gdm3.service display-manager.service lightdm.service sddm.service 2>/dev/null || true

for n in 1 2 3 4 5 6; do
    systemctl --root="$ROOTFS" mask "getty@tty${n}.service" 2>/dev/null || true
    rm -rf "$ROOTFS/etc/systemd/system/getty@tty${n}.service.d"
done

for tty in ttyTCU0 ttyS0 ttyGS0; do
    systemctl --root="$ROOTFS" disable "serial-getty@${tty}.service" 2>/dev/null || true
    systemctl --root="$ROOTFS" mask "serial-getty@${tty}.service" 2>/dev/null || true
    rm -rf "$ROOTFS/etc/systemd/system/serial-getty@${tty}.service.d"
done

systemctl --root="$ROOTFS" enable ssh.service 2>/dev/null || true
systemctl --root="$ROOTFS" enable systemd-timesyncd.service 2>/dev/null || true

echo "[6/9] Quiet boot"
EXTLINUX="$ROOTFS/boot/extlinux/extlinux.conf"

if [ -f "$EXTLINUX" ]; then
    cp "$EXTLINUX" "$EXTLINUX.bak.hardening"

    sed -i \
      -e 's/console=ttyTCU0,115200//g' \
      -e 's/console=tty0//g' \
      -e 's/mminit_loglevel=4/mminit_loglevel=0/g' \
      "$EXTLINUX"

    if ! grep -q "quiet loglevel=0" "$EXTLINUX"; then
        sed -i '/^[[:space:]]*APPEND / s/$/ quiet loglevel=0 systemd.show_status=false udev.log_level=3 vt.global_cursor_default=0/' "$EXTLINUX"
    fi
else
    echo "WARNING: extlinux.conf not found: $EXTLINUX"
fi

echo "[7/9] Block USB storage but keep USB cameras"
install -d -m 755 "$ROOTFS/usr/local/sbin"

cat > "$ROOTFS/usr/local/sbin/block-usb-storage.sh" <<'EOF'
#!/bin/sh

LOGGER_TAG="block-usb-storage"

logger -t "$LOGGER_TAG" "Blocking USB storage interface: DEVPATH=$DEVPATH DEVNAME=$DEVNAME"

if [ -n "${DEVPATH:-}" ] && [ -e "/sys$DEVPATH/authorized" ]; then
    echo 0 > "/sys$DEVPATH/authorized" 2>/dev/null || true
fi

if [ -n "${DEVPATH:-}" ]; then
    PARENT="$(dirname "/sys$DEVPATH")"
    if [ -e "$PARENT/authorized" ]; then
        echo 0 > "$PARENT/authorized" 2>/dev/null || true
    fi
fi

if [ -n "${DEVNAME:-}" ]; then
    BASE="$(basename "$DEVNAME")"

    case "$BASE" in
        sd[a-z])
            if [ -e "/sys/block/$BASE/device/delete" ]; then
                echo 1 > "/sys/block/$BASE/device/delete" 2>/dev/null || true
            fi
            ;;
        sd[a-z][0-9]*)
            DISK="$(echo "$BASE" | sed 's/[0-9]*$//')"
            if [ -e "/sys/block/$DISK/device/delete" ]; then
                echo 1 > "/sys/block/$DISK/device/delete" 2>/dev/null || true
            fi
            ;;
    esac
fi

exit 0
EOF

chmod 755 "$ROOTFS/usr/local/sbin/block-usb-storage.sh"

cat > "$ROOTFS/etc/udev/rules.d/99-block-usb-storage.rules" <<'EOF'
ACTION=="add", SUBSYSTEM=="usb", DEVTYPE=="usb_interface", ATTR{bInterfaceClass}=="08", RUN+="/usr/local/sbin/block-usb-storage.sh"
ACTION=="add", SUBSYSTEM=="block", ENV{ID_BUS}=="usb", RUN+="/usr/local/sbin/block-usb-storage.sh"
ACTION=="change", SUBSYSTEM=="block", ENV{ID_BUS}=="usb", RUN+="/usr/local/sbin/block-usb-storage.sh"
EOF

# Do not blacklist usb-storage/uas via modprobe for encrypted boot.
# The NVIDIA encrypted initrd may need to probe USB drivers and may not contain /bin/false.
# USB mass storage is blocked later from the real rootfs through udev.
rm -f "$ROOTFS/etc/modprobe.d/99-disable-usb-storage.conf" 2>/dev/null || true
rm -f "$ROOTFS/usr/lib/modprobe.d/99-disable-usb-storage.conf" 2>/dev/null || true

# Do NOT block camera-related modules:
# uvcvideo, videobuf2_*, usbcore, xhci_*, usbhid
rm -f "$ROOTFS/etc/modprobe.d/disable-usbhid.conf" 2>/dev/null || true
rm -f "$ROOTFS/usr/lib/modprobe.d/disable-usbhid.conf" 2>/dev/null || true

echo "[8/9] Regenerate clean initrd"

if [ -x "$ROOTFS/bin/bash" ]; then
    chroot "$ROOTFS" /bin/bash -lc '
set -e

rm -f /etc/modprobe.d/99-disable-usb-storage.conf
rm -f /usr/lib/modprobe.d/99-disable-usb-storage.conf
rm -f /etc/modprobe.d/disable-usbhid.conf
rm -f /usr/lib/modprobe.d/disable-usbhid.conf

rm -f /boot/initrd
rm -f /boot/initrd.img-5.15.185-tegra

update-initramfs -c -k 5.15.185-tegra
'

    if [ -f "$ROOTFS/boot/initrd.img-5.15.185-tegra" ]; then
        cp "$ROOTFS/boot/initrd.img-5.15.185-tegra" "$ROOTFS/boot/initrd"
    else
        echo "ERROR: initrd.img-5.15.185-tegra was not generated"
        exit 1
    fi

    if lsinitramfs "$ROOTFS/boot/initrd" | grep -q '99-disable-usb-storage'; then
        echo "ERROR: stale 99-disable-usb-storage.conf found inside initrd"
        exit 1
    fi

    echo "OK: initrd clean"
else
    echo "ERROR: $ROOTFS/bin/bash not found or not executable"
    exit 1
fi

echo "[9/9] Done"
echo "L4T_DIR:      $L4T_DIR"
echo "ROOTFS:       $ROOTFS"
echo "USER:         $USER_NAME"
echo "HOSTNAME:     $HOSTNAME"
echo "IP:           $IP_CIDR"
echo "GATEWAY:      $GATEWAY"
echo "DNS:          $DNS"
echo "PUBKEYS_FILE: $PUBKEYS_FILE"
