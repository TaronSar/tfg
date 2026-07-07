# USB Boot Troubleshooting — Veronte Kai

## Estado actual

- **Flash**: OK (MB1/MB2/UEFI boota limpio)
- **UEFI**: Cae al UEFI Shell (no encuentra kernel)
- **USB**: El SD card reader NO enumera en UEFI
- **Ethernet**: MAC `4CBB4713D07E` visible en UEFI -> **funciona**

---

## Por qué no arranca USB

El `L4TConfiguration.dtbo` tiene `DefaultBootPriority = "usb,nvme,emmc,sd,ufs"` — USB ya es **primero**. El problema es que el controlador XHCI no inicializa el dispositivo en el tiempo que espera UEFI, o el lector SD tiene incompatibilidad de enumeración.

---

## Opción 1: Arreglar el terminal UEFI Shell (requisito para opciones manuales)

El script `putty_FPGA_terminal.sh` con `plink` tiene problemas de eco/line-ending con UEFI.

**Usar `screen` en su lugar:**
```bash
# Ver qué /dev/ttyUSBx es la Veronte Kai
dmesg | grep -i tty | tail -10

# Conectar (reemplaza ttyUSB0 con tu dispositivo)
screen /dev/ttyUSB0 115200

# Para salir de screen: Ctrl+A, luego K
```

Con `screen`, los comandos funcionan directamente en el UEFI shell.

---

## Opción 2: Comandos UEFI Shell para forzar enumeración USB

Una vez que el terminal funcione, en el UEFI shell (`Shell>`):

```shell
# 1. Forzar reconexión de todos los drivers (incluye XHCI)
connect -r

# 2. Esperar 8 segundos para que el lector SD enumere
stall 8000000

# 3. Re-escanear dispositivos de almacenamiento
map -r

# 4. Ver si apareció un nuevo filesystem (FS2, FS3, etc.)
map

# 5a. Si apareció FS2 (o FSx), arrancar desde él:
FS2:\EFI\BOOT\bootaa64.efi

# 5b. O buscar extlinux.conf manualmente:
FS2:\boot\extlinux\extlinux.conf
```

Si después del `map -r` aparece un nuevo `FSx` -> el lector funciona pero necesitaba tiempo extra.

---

## Opción 3: HTTP Boot via Ethernet (MÁS FIABLE — no requiere USB en UEFI)

El Ethernet funciona en UEFI. Pasos:

### En el host:
```bash
# Instalar dependencias
sudo apt install dnsmasq python3

# Preparar SD card con rootfs primero
sudo ~/Documents/Jetson/veronte_kai/scripts/prepare_sdcard.sh /dev/sdX

# Arrancar servidor HTTP Boot (en otra terminal, como root)
sudo ~/Documents/Jetson/veronte_kai/scripts/setup_http_boot.sh eth0
```

### En la Veronte Kai:
1. Conecta el cable Ethernet (host ↔ Veronte Kai)
2. Conecta el lector USB-SD con la SD card preparada
3. Enciende sin modo recovery

**Flujo resultante:**
- UEFI -> HTTP Boot -> kernel descargado desde host
- Kernel Linux arranca -> **Linux sí inicializa XHCI** -> ve el lector como `/dev/sda`
- Linux monta `/dev/sda1` (SD card) como rootfs
- Sistema arranca completamente

---

## Opción 4: USB Flash Drive directa (sin SD card reader)

Los pendrives USB enumeran mucho más rápido que los lectores de tarjetas:

```bash
# Copiar solo /boot a un pendrive USB pequeño (>=2GB, ext4)
sudo ~/Documents/Jetson/veronte_kai/scripts/prepare_sdcard.sh /dev/sdX

# La SD card en el lector USB tendría el rootfs completo
# El pendrive USB tendría /boot con kernel + extlinux.conf
# extlinux.conf apunta root=/dev/sdb1 (o sda1 dependiendo del orden de detección)
```

**Nota**: Con dos dispositivos USB, el kernel los asigna por orden de detección.
Puede ser `/dev/sda` (pendrive) y `/dev/sdb` (lector SD) o al revés.
Ajustar `root=` en extlinux.conf tras el primer boot.

---

## Diagnóstico: ¿Qué dice el serial durante el boot?

Para ver por qué falla USB, conecta el serial ANTES de encender:

```bash
screen /dev/ttyUSB0 115200
# Luego enciende la Veronte Kai
# Verás logs de MB1/MB2/UEFI
# Busca mensajes como:
#   "Checking USB..."
#   "USB device not found"  ← timeout de XHCI
#   "XHCI init failed"      ← error de hardware
#   "HTTP Boot"             ← si activa el fallback de red
```

---

## Opción 5: Aumentar timeout USB en UEFI (requiere re-flash)

Si el problema es un timeout corto, podemos modificar `L4TConfiguration.dtbo` para añadir un delay mayor antes de buscar dispositivos USB. Esto requiere:
1. Modificar el DTBO (necesito los strings exactos del UEFI firmware)
2. Re-ejecutar `./build_veronte_kai.sh` 
3. Re-flashear con `./flash_veronte_kai.sh`

Contacta si quieres explorar esta opción.


## SOM produccion VS SOM kit

Con SOM de devkit en carrier Veronte Kai, la SD aparece como `mmcblk0p1`. Cambiar `root=/dev/sda1` -> `root=/dev/mmcblk0p1` en extlinux.conf |
