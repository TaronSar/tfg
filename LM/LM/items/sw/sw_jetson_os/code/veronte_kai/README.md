# Veronte Kai - Build System

Carrier custom para **Jetson Orin Nano P3767-0003** basada en L4T R36.5.0 (JetPack 6.0).

## Requisitos previos

```bash
sudo apt-get install -y qemu-user-static lz4 libxml2-utils device-tree-compiler quilt python3
```

El BSP de NVIDIA debe estar extraído y con el rootfs aplicado:
```bash
cd ~/Documents/Jetson/Linux_for_Tegra
sudo ./apply_binaries.sh
```

## Uso - one-liner

```bash
cd ~/Documents/Jetson/veronte_kai/scripts
./build_veronte_kai.sh
```

Opciones:
| Flag | Efecto |
|---|---|
| `--dry-run` | Simula todo sin modificar nada |
| `--clean` | Revierte parches antes de empezar |
| `--skip-patch` | Salta Stage 2 (parches ya aplicados) |
| `--only-stage N` | Ejecuta solo Stage N (1-4) |
| `--diagnose` | Muestra estado del entorno y sale |

## Flasheo

**Solo ejecutar cuando el módulo esté en modo RECOVERY:**
```bash
cd ~/Documents/Jetson/veronte_kai/scripts
./flash_veronte_kai.sh
```
> Este script se genera automáticamente en Stage 4. NO editarlo a mano.

## Estructura de parches

| Parche | Archivo BSP modificado | Cambio |
|---|---|---|
| `0001` | `bootloader/generic/BCT/tegra234-mb1-bct-pinmux-p3767-{dp,hdmi}-a03.dtsi` | Pin 127: `gen2_i2c` -> `gp` + `PULL_UP` |
| `0002` | `veronte_kai.conf` (nuevo) | Conf para SKU 0003 + CMDLINE_ADD |
| `0003` | `rootfs/boot/extlinux/extlinux.conf` | `root=/dev/sda1 rootwait` |

## Revertir cambios

```bash
cd ~/Documents/Jetson/veronte_kai/scripts
./revert_patches.sh
```

## Diagnóstico del Bus Spin

Ver `docs/pinmux_changes.md` y `docs/eeprom_bypass.md` para el análisis completo.
**Stage 0 es obligatorio** antes del primer flasheo - leer `docs/diagnosis_report.md`.
