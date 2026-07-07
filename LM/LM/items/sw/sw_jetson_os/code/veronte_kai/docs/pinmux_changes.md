# Cambios de Pinmux — Veronte Kai

## Pin 127: GEN2_I2C → GPIO con pull-up

### Identificación del pin

| Campo | Valor |
|---|---|
| Nombre NVIDIA | `gen2_i2c_scl_pcc7` / `gen2_i2c_sda_pdd0` |
| Bus I2C | I2C2 (GEN2_I2C) |
| Archivos BSP | `tegra234-mb1-bct-pinmux-p3767-dp-a03.dtsi` y `…-hdmi-a03.dtsi` |

### Por qué el cambio

La carrier Veronte Kai no dispone de resistencias pull-up externas en el bus I2C2.
El BSP de NVIDIA configura estos pines con `function = "i2c2"` y `pull = TEGRA_PIN_PULL_NONE`,
lo que deja el bus flotando al no haber pull-ups externos. Esto puede provocar:

- Lecturas espurias / glitches en el bus durante el boot.
- En casos extremos, bloqueo del boot si algún periférico monitoriza I2C2.

### Cambio aplicado (parche 0001)

```diff
 gen2_i2c_scl_pcc7 {
     nvidia,pins = "gen2_i2c_scl_pcc7";
-    nvidia,function = "i2c2";
-    nvidia,pull = <TEGRA_PIN_PULL_NONE>;
+    nvidia,function = "gp";
+    nvidia,pull = <TEGRA_PIN_PULL_UP>;
     nvidia,tristate = <TEGRA_PIN_DISABLE>;
     nvidia,enable-input = <TEGRA_PIN_ENABLE>;
     ...
 };
```

Mismo cambio para `gen2_i2c_sda_pdd0`.

### Consecuencias

- I2C2 queda deshabilitado a nivel de periférico SoC.
- Los pines se comportan como GPIO de entrada con pull-up interno activo.
- El bus queda en estado alto (idle correcto), eliminando los glitches.

### ⚠️ Nota sobre el síntoma Bus Spin observado

El `Bus Spin` observado en el log (`eeprom: Failed to read I2C slave device`) **puede no
estar relacionado con I2C2**. Según el BCT de R36.5:

- `cvm_eeprom_i2c_instance = <0>` → I2C1 (interno del módulo)
- `cvb_eeprom_i2c_instance = <0>` → I2C1
- PMIC usa I2C5

**Se requiere Stage 0 (log UART completo)** para confirmar qué bus está colgado antes de
asumir que este parche resuelve el síntoma.
