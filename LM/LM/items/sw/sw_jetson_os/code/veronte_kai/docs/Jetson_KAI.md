# Veronte Kai - Jetson Orin Nano

**Módulo**: Jetson Orin Nano P3767-0003 (4 GB)  
**BSP**: L4T R36.5.0  
**Estado**: ✅ Operativo - Flash QSPI + boot desde SD card + red + SSH

---

## Hardware

| Componente | Detalle |
|---|---|
| Módulo | Jetson Orin Nano P3767-0003 (4 GB RAM) |
| Carrier | Veronte Kai (custom Embention) |
| BOARDID / SKU | 3767 / 0003 |
| FAB / REV | 000 / A.0 |
| Flash | QSPI interno (bootloaders únicamente) |
| Rootfs | SD card via lector USB (carrier Veronte Kai) |
| Ethernet | Realtek RTL8168, MAC `4C:BB:47:13:D0:7E` |

---

## Puesta en marcha - placa nueva

### Requisitos previos
- BSP L4T R36.5.0 descomprimido en `~/Documents/Jetson/Linux_for_Tegra/`
- Rootfs Ubuntu 22.04 aplicado (`apply_binaries.sh` ejecutado)
- Repositorio `veronte_kai/` en el mismo nivel que `Linux_for_Tegra/`

### 1. Flashear QSPI

```bash
# Poner módulo en modo RECOVERY: mantener REC pulsado y pulsar RESET
lsusb | grep NVIDIA   # debe mostrar 0955:7523

cd veronte_kai/scripts
./flash_veronte_kai.sh
```

### 2. Preparar SD card con rootfs

```bash
# Conectar SD card al host, identificar dispositivo
lsblk | grep -i sd

sudo ./prepare_sdcard.sh /dev/sdX
```

### 3. Configurar extlinux.conf en la SD

Montar la partición APP (sda1) y editar:

```bash
sudo mount /dev/sda1 /mnt/kai
sudo nano /mnt/kai/boot/extlinux/extlinux.conf
sudo umount /mnt/kai
```

**extlinux.conf:**
```
TIMEOUT 30
DEFAULT primary

MENU TITLE L4T boot options

LABEL primary
      MENU LABEL primary kernel
      LINUX /boot/Image
      INITRD /boot/initrd
      APPEND ${cbootargs} root=/dev/sda1 rw rootwait rootdelay=5 rootfstype=ext4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 video=efifb:off console=tty0 efi=runtime
```

> **Nota:** Si se usa un SOM del **devkit p3768** (con slot microSD nativo) en el carrier Veronte Kai,
> la SD aparece como `/dev/mmcblk0p1`. Cambiar `root=/dev/sda1` -> `root=/dev/mmcblk0p1`.

> **Nota:** La línea `FDT` no es necesaria - el QSPI inyecta el DTB correcto via `${cbootargs}`.

### 4. Arrancar y configurar red

Conectar al serial:
```bash
screen /dev/ttyUSB0 115200
```

Configurar IP estática con nmtui:
```bash
sudo nmtui
```

Configuración de red:
- IP: `192.168.3.30/22`
- Gateway: `192.168.0.1`
- DNS: `1.1.1.1`

Acceso SSH:
```bash
ssh nvidia@192.168.3.30
```

---

## Parches BSP aplicados

### 0001 - Pinmux i2c2 -> GPIO (MB1)

**Archivos:** `bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-{dp,hdmi}-a03.dtsi`

Pines `gen2_i2c_scl_pcc7` y `gen2_i2c_sda_pdd0`: `function=i2c2` + `pull=NONE` -> `function=gp` + `pull=PULL_UP`.

La Veronte Kai no tiene dispositivos en I2C2. Sin este parche MB1 hace Bus Spin y el arranque se cuelga.

### 0002 - veronte_kai.conf

Archivo de configuración de flash para el carrier Veronte Kai:
- `EMMC_CFG=flash_t234_qspi.xml` - solo QSPI, sin SDMMC4 ni NVMe
- `DTB_FILE=tegra234-p3767-0003-veronte-kai.dtb` - DTB custom con fix USB
- `BOARDSKU=0003` - Orin Nano 4 GB

### EEPROM bypass

Ya incluido en upstream R36.5 - no requiere parche:
```
cvm_eeprom_read_size = <0x0>;
cvb_eeprom_read_size = <0x0>;
```

---

## DTB custom - Fix USB

**Archivo:** `Linux_for_Tegra/kernel/dtb/tegra234-p3767-0003-veronte-kai.dtb`  
**Fuente:** `overlays/tegra234-p3767-0003-veronte-kai-usb.dts`

El carrier Veronte Kai conecta el USB 3.0 Type-A usando:
- HS lanes: `USB0_D_N/P` (pines módulo 109/111) -> padctl `usb2-0`
- SS lanes: `USBSS0` (pines módulo 161/163/166/168) -> padctl `usb3-0`

El DTB del devkit p3768 tenía el companion erróneo (`usb3-0` -> `usb2-1`). Cambios aplicados:

| Nodo | Propiedad | Antes | Después |
|---|---|---|---|
| `padctl/ports/usb2-0` | `mode` | `"otg"` | `"host"` |
| `padctl/ports/usb2-0` | `usb-role-switch` | presente | eliminada |
| `padctl/ports/usb3-0` | `nvidia,usb2-companion` | `<1>` | `<0>` |
| `padctl/ports/usb3-1` | `nvidia,usb2-companion` | `<0>` | `<1>` |
| `usb@3550000` (XUDC) | `status` | `"okay"` | `"disabled"` |
| `fusb301@25` (TypeC IC) | `status` | `"okay"` | `"disabled"` |

---

## Reparar SD card (journal ext4 corrupto)

Síntomas: `EXT4-fs error: Detected aborted journal` / sistema monta en read-only.  
Causa: apagado brusco. Solución: **siempre `sudo poweroff`** antes de sacar la SD.

```bash
sudo umount /dev/sda1 2>/dev/null
sudo fsck.ext4 -y /dev/sda1
sudo fsck.ext4 -n /dev/sda1   # debe decir "clean"
```

---

## Referencia rápida

```bash
# Serial
screen /dev/ttyUSB0 115200        # salir: Ctrl+A, K

# Modo recovery
lsusb | grep NVIDIA               # 0955:7523 = OK

# Flash
cd veronte_kai/scripts && ./flash_veronte_kai.sh

# Montar SD desde host
sudo mount /dev/sda1 /mnt/kai
sudo umount /mnt/kai
```
