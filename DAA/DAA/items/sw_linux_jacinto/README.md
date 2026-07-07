# Pasos para Flashear la SD

Esta guía detalla el proceso para crear una tarjeta SD de arranque para la EVM J784S4, incluyendo los perfiles de Device Tree personalizados para simular los SoCs TDA4AP-Q1, TDA4VP-Q1, TDA4AH-Q1 y TDA4VH-Q1.

## Requisitos

* SDK de Linux para la familia Jacinto 7: `PROCESSOR-SDK-LINUX-J784S4` **versión 11.01.00.03**. [Descargar aquí](https://www.ti.com/tool/download/PROCESSOR-SDK-LINUX-J784S4).
* Una tarjeta MicroSD de **16 GB o superior**.

## Pasos

### Paso 1: Preparar el Entorno de Compilación

Este paso prepara el SDK de TI para que reconozca nuestros ficheros de Device Tree (`.dts`) personalizados.

* Ejecuta el script `build.sh` ubicado en nuestro repositorio.
    ```bash
    ./DAA/items/sw_linux_jacinto/build.sh
    ```
    Este script se encarga de:
    1.  Copiar los ficheros `.dts` de nuestros perfiles (`-tda4ap`,`-tda4vp`, `-tda4ah` y `-tda4vh` ) al directorio de fuentes del kernel del SDK.
    2.  Modificar el fichero `Rules.make` del SDK para que el sistema de compilación incluya estos nuevos ficheros en el proceso.
    3. Compila el Decive Tree

### Paso 2: Crear la Tarjeta SD Base

Este paso formatea la tarjeta SD y copia en ella la imagen de Linux por defecto del SDK.

* Ejecuta el script `create-sdcard.sh` proporcionado por TI. Sigue las instrucciones que aparecerán en pantalla para seleccionar el dispositivo de tu tarjeta SD. **¡PRECAUCIÓN: Este paso borrará todo el contenido de la tarjeta seleccionada!**
    ```bash
    cd /opt/ti/sdk-linux-j784s4-evm-11-01-00-03/
    sudo ./bin/create-sdcard.sh
    ```
    *Referencia oficial del SDK:* [Create SD Card With Default Images](https://software-dl.ti.com/jacinto7/esd/processor-sdk-linux-j784s4/11_01_00_03/exports/docs/linux/Overview/Processor_SDK_Linux_create_SD_card.html#create-sd-card-with-default-images-using-script)

### Paso 3: Aplicar la Personalización a la Tarjeta SD

Ahora, con la tarjeta SD base ya creada, vamos a añadir nuestros perfiles personalizados.

1.  **Copia los Device Trees Compilados:** Copia los ficheros `.dtb` que generaste en el Paso 2 al directorio `boot/dtb/` de la tarjeta SD. Los compilados se encuentran en `/opt/ti/sdk-linux-j784s4-evm-11-01-00-03/board-support/ti-linux-kernel-6.12.35+git-ti/arch/arm64/boot/dts/ti`.

2.  **Configura `uEnv.txt`:** Copia el fichero `uEnv.txt` desde nuestro repositorio a la raíz de la partición `boot`, reemplazando el que creó el script.
    ```bash
    cp DAA/items/sw_linux_jacinto/uEnv.txt $BOOT_PART/
    ```
    Para seleccionar el perfil de hardware que deseas probar, **edita el fichero `uEnv.txt`** en la tarjeta SD y modifica la línea `fdtfile` correspondiente al modelo que quieres simular.

    **Ejemplo del contenido de `uEnv.txt`:**
    ```makefile
        dorprocboot=1
        fdtfile=boot/dtb/k3-j784s4-evm-tda4ap-profile.dtb
        overlay1=boot/ti/k3-j784s4-evm-ethfw.dtbo
        overlay2=boot/ti/k3-j784s4-vision-apps.dtbo

        addr_overlay1=0x83000000
        addr_overlay2=0x83100000

        uenvcmd= \
          echo "--- Ejecutando arranque personalizado desde uEnv.txt ---"; \
          echo "Cargando Kernel..."; \
          load mmc 1:1 ${loadaddr} Image; \
          echo "Cargando Device Tree Base: ${fdtfile}"; \
          load mmc 1:1 ${fdtaddr} ${fdtfile}; \
          echo "Cargando Overlay 1: ${overlay1}"; \
          load mmc 1:1 ${addr_overlay1} ${overlay1}; \
          echo "Cargando Overlay 2: ${overlay2}"; \
          load mmc 1:1 ${addr_overlay2} ${overlay2}; \
          echo "Arrancando Linux..."; \
          booti ${loadaddr} - ${fdtaddr} ${addr_overlay1} ${addr_overlay2};
    ```
Dependiendo del modelo que quieras modificaremos `fdtfile` para que se llame igual que el `dtb` correspondiente a cada modelo.