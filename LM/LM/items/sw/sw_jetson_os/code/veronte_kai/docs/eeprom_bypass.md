# EEPROM Bypass — Veronte Kai

## Estado: YA VIENE DE FÁBRICA en L4T R36.5.0 — No es un parche nuestro

### Verificación

```bash
grep -E 'cvm_eeprom_read_size|cvb_eeprom_read_size' \
  ~/Documents/Jetson/Linux_for_Tegra/bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts
```
Resultado esperado (upstream R36.5):
```
cvm_eeprom_read_size = <0x0>;
cvb_eeprom_read_size = <0x0>;
```

### Qué significa

Con `read_size = <0x0>`, MB2 no intenta leer las EEPROMs del carrier/módulo para
identificar la placa. La identidad se suministra en tiempo de flasheo mediante variables
de entorno (`BOARDID`, `BOARDSKU`, `FAB`, `BOARDREV`).

### Por qué es importante para Veronte Kai

La carrier Veronte Kai es custom y no tiene los mismos buses I2C que el devkit P3768.
Si MB2 intentase leer las EEPROMs por I2C, el bus podría colgarse al no encontrar los
dispositivos esperados.

El wrapper `flash_veronte_kai.sh` siempre exporta:
```bash
BOARDID=3767  BOARDSKU=0003  FAB=000  BOARDREV=A.0
```

### Porting a futuras versiones de BSP

Si al actualizar el BSP los valores vuelven a ser no-cero:
1. Restaurar `cvm_eeprom_read_size = <0x0>` y `cvb_eeprom_read_size = <0x0>` en
   `bootloader/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts`.
2. Añadir el parche correspondiente a `patches/series` (ver
   `overlays/mb2/mb2-bct-eeprom-bypass.dtsi` como referencia).
