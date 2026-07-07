<!-- ## 📑 Índice -->
# Index

1. [Introduction](#1-introduction)

2. [Previous steps and installs](#2-previous-steps-and-required-installations)

3. [Development and compiling setup](#3-development-and-compiling-setup)
    
    3.1. [Setup cross-compile](#31-setup-cross-compile)
    
    3.2. [Setup x86-64](#32-setup-x86-64)
    
    3.3. [Setup Nvidia](#33-setup-nvidia)

4. [VBN deployment](#4-vbn-deployment)
    
    4.1. [Viewer deployment](#41-viewer-deployment)

    4.2. [Remote debugging](#42-remote-debugging)

# 1. Introduction
El entorno desarrollo utilizado para trabajar en GNSS Denied utiliza contenedores Docker para encapsular el conjunto de dependencias requeridas. 

Actualmente se trabaja con tres setups diferentes que se emplean en función de las necesidades y las pruebas que se realizan. Por un lado, se dispone de un setup de compilación cruzada para los productos dependientes de Xilinx, un setup local para x86-64, y un setup orientado a trabajar en la Nvidia Jetson para prototipado rápido.

En las siguientes secciones se describen más en detalle estos diferentes entornos de trabajo.

# 2. Previous steps and required installations
## Install Docker
[Install docker](/docs/VBN/sw_env_setup.md)

## Install Nvidia Docker
[Install nvidia-docker](/docs/VBN/sw_env_setup.md)

# 3. Development and compiling setup
El primer paso, habiendo ya instalado previamente Docker y Nvidia-docker, es clonar el repositorio de DAA (en la ruta `/$HOME/`), con sus correspondientes submódulos (para VBN, únicamente es necesario el submódulo de *Vlibs*). 

Si se ha clonado el repo sin definir los submódulos, ejecutar los siguientes comandos desde la carpeta raíz del repo en local:

```
git submodule init
git submodule update items/Vlibs
git checkout feature/DAA/74_vbn
```

>**NOTA**: Este último comando es necesario llevarlo a cabo para movernos a la rama `feature/DAA/74_vbn` de Vlibs, que es la utilizada para el proyecto. Ejecutar el comando desde la ruta `/$HOME/DAA/items/Vlibs/`.

Una vez configurado el repositorio local, en función del tipo de compilación o el entorno que se quiera levantar, es necesario seguir unos pasos u otros.

Para el proyecto, se dispone de 3 setups diferentes, algunos para desarrollo y otros para compilación, con diferentes arquitecturas:

- **[Setup de compilación cruzada](#setup-cross-compile)**. Este setup permite compilar desde una arquitectura nativa x86-64 para una arquitectura final arm64 (aarch64).

- **[Setup en x86-64](#setup-x86)**. Este setup permite compilar para x86-64.

- **[Setup en Nvidia](#setup-nvidia)**. Este setup permite compilar para la Nvidia Jetson en una arquitectura aarch64 host; es el contenedor utilizado para el desarrolo de la mayor parte del proyecto.


## 3.1. Setup Cross-compile

El entorno de cross-compile permite compilar desde una arquitectura nativa x86-64 para una arquitectura arm64 (aarch64). Para ello, se emplea un contenedor con todas las dependencias y herramientas necesarias. 

Para construir la imagen docker utilizada para la compilación cruzada del proyecto  se han de seguir los siguientes pasos:

1. Moverse al directorio `/$HOME/DAA/items/sw_gnssdenied/code/project/docker-cross`.

2. Seguir las instrucciones en [este README](https://github.com/embention/DAA/tree/develop/items/sw_gnssdenied/code/project/docker-cross) para compilar la imagen docker. Es necesario descargar de [aquí](https://drive.google.com/drive/folders/1Q7qIh1OwxYHMg__nLa5v7e1Cq-LvDAF-?usp=drive_link) los comprimidos con las toolbox, lo cual está correctamente explicado en el README.

Una vez se ha compilado la imagen docker, ya se puede proceder a lanzarlo y compilar el proyecto, para lo cual hay 2 opciones posibles.

### Using compiling scripts (*from scratch*)

1. Lanzar el docker ejecutando `VLIBS_DIR=/$HOME/DAA/items/Vlibs PRJ_DIR=/$HOME/DAA ./run.sh` en la ruta `/$HOME/DAA/items/sw_gnssdenied/code/project/docker-cross`.

<a id="mover-carpeta-scripts"></a>

2. Una vez ejecutado el contenedor, navegar a la ruta `/workspace/items/sw_gnssdenied/code/project/scripts` dentro del mismo.

<a id="compilar-scratch"></a>

3. Ejecutar en el orden indicado los siguientes comandos:

    - `./cross_build_vlibs.sh`  (Compilación de los items necesarios de Vlibs)

    - `./cross_build_coproc.sh` (Compilación del coprocesador)

    - `./cross_build_wvlibs.sh` (Compilación del wrapper de Vlibs)

    - `./cross_build_vproto.sh` (Compilación del item sw_vproto)

    - `./cross_build_orb_slam3.sh` (Compilación de las librerías de GNSS Denied)

    - `./cross_build_test.sh plnx/ft_multithread`   (Compilación del ejecutable de GNSS Denied)

>El resultado final de este paso será la generación de un archivo ejecutable `vbn` en la ruta `/workspace/items/sw_gnssdenied/code/project/cmake/build`(**dentro del docker**), así como de un archivo `libORB_SLAM3.so` en la ruta `/workspace/items/sw_gnssdenied/items/sw_orbslam/lib/`.  

<a id="copiar-archivos"></a>

4. Copiar los archivos generados a la placa sobre la que se va a ejecutar (además de un archivo .yaml de configuración):

    ```
    scp -o HostKeyAlgorithms=ssh-rsa items/sw_gnssdenied/code/project/cmake/build/vbn  root@192.168.1.162:/home/root

    scp -o HostKeyAlgorithms=ssh-rsa items/sw_gnssdenied/items/sw_orbslam/lib/libORB_SLAM3.so  root@192.168.1.162:/usr/lib

    scp -o HostKeyAlgorithms=ssh-rsa items/sw_gnssdenied/code/conf/vbn_config.yaml  root@192.168.1.162:/home/root
    ```

>**NOTA**: Las instrucciones copiadas se han ejecutado desde la carpeta del repo (`.../DAA/`), y para copiar los archivos a la PCB 107 con la IP 192.168.1.162. 
Por otro lado, el archivo de configuración también está "hardcodeado" para las pruebas que utilizamos a diario, con las rutas donde se encuentran los archivos requeridos en la PCB 107.

### Using VSCode tasks

Esta segunda opción consiste en utilizar las herramientas y extensiones disponibles en VSCode para realizar una compilación más *de alto nivel*, sin necesidad de conocer tan detalladamente todos los scripts e items que están implicados en la compilación del proyecto. 

1. Lanzar el docker ejecutando `VLIBS_DIR=/$HOME/DAA/items/Vlibs PRJ_DIR=/$HOME/DAA ./run.sh` en la ruta `/$HOME/DAA/items/sw_gnssdenied/code/project/docker-cross`.

2. Desde vscode, instalar los plugins para docker. Una vez se encuentre en ejecución el contenedor ejecutar la opción "**Attach Visual Studio Code**". 

3. Copiar los archivos `tasks.json` y `launch.json` desde la carpeta de otro usuario a la carpeta `/$HOME/DAA/items/sw_gnssdenied/code/project/cmake/vscode/$USER` o desde Visual Studio code a la carpeta `.vscode`.

4. Para compilar todos el software pulsar **Ctrl+Shift+b** y seleccionar la opción "**buils sw_gnssdenied and send**". Esta opción compilará los items `Vlibs`, `coproc`, `wvlibs`, `sw_vproto`, `sw_orbslam`, así como el ejecutable `vbn` y enviará el resultado a la placa correspondiente. Será necesario ajustar la IP de la placa para este envío. Este paso es equivalente a los pasos [3](#compilar-scratch) y [4](#copiar-archivos) de la sección anterior.

# 3.2. Setup x86-64

El entorno de x86-64 permite compilar directamente sobre una máquina local para su propia arquitectura en x86-64. 

Es el entorno empleado para compilar y ejecutar el visualizador por red que permite analizar y depurar visualmente el funcionamiento del VBN. Dicho *viewer* corre sobre un PC en local, y recibe en tiempo real la información generada por el pipeline principal del VBN, corriendo sobre una placa.

Los pasos a seguir son prácticamente idénticos a los descritos para el entorno de cross-compile, pero con ligeras modificaciones.

Para construir la imagen docker utilizada en este entorno se han de seguir los siguientes pasos:

1. Moverse al directorio `/$HOME/DAA/items/sw_gnssdenied/code/project/docker/`.

2. Ejecutar el script `./build.sh` para compilar la imagen docker.

3. Lanzar el docker ejecutando el comando `./run-x86.sh` en la misma ruta.

4. Tras levantar el docker, para compilar los items del proyecto se han de seguir los mismos pasos en [2](#mover-carpeta-scripts), [3](#compilar-scratch) y [4](#copiar-archivos) de la sección [setup cross-compile](#31-setup-cross-compile).

Para compilar el visualizador, es necesario ejecutar la última instrucción modificando el objetivo de la compilación:

```./cross_build_test.sh plnx/viewer```

>**NOTA**:Por el momento, las tareas para poder llevar a cabo la compilación desde VSCode se encuentran desactualizadas.


# 3.3. Setup Nvidia

El entorno de Nvidia Jetson es el entorno sobre el cual se realiza la mayor parte del desarrollo software, debido a la capacidad de realizar un prototipado rápido y cómodo. En este entorno se compila desde la propia Nvidia Jetson en local, en aarch64, para ejecutar sobre la misma arquitectura, también en local.

Los pasos a seguir son prácticamente idénticos a los descritos para el entorno de cross-compile, pero con ligeras modificaciones.

Para construir la imagen docker utilizada en este entorno se han de seguir los siguientes pasos:

1. Moverse al directorio `/$HOME/DAA/items/sw_gnssdenied/code/project/docker/`.

2. Ejecutar el script `./build.sh` para compilar la imagen docker.

3. Moverse a la ruta `/$HOME/DAA/items/sw_gnssdenied/code/project/docker-jetson/`.

4. Lanzar el docker ejecutando el comando `./run.sh`.

5. Tras levantar el docker, para compilar los items del proyecto se han de seguir los mismos pasos en [2](#mover-carpeta-scripts) y [3](#compilar-scratch) de la sección [setup cross-compile](#31-setup-cross-compile). No es necesario el paso 4, pues no hay que copiar los archivos ya que la ejecución se lleva a cabo sobre la propia Nvidia Jetson.

>**NOTA**:Por el momento, las tareas para poder llevar a cabo la compilación desde VSCode se encuentran desactualizadas.

# 4. VBN deployment

Actualmente, hay 3 posibles modos de ejecución del VBN. En esta sección se describe cada uno de ellos, así como el comando para lanzarlos.


>**NOTA**: Los comandos especificados a continuación son para la ejecución sobre la PCB 107. En caso de ejecución sobre otro dispositivo, sería necesario modificarlos. Dichos comandos han de ejecutarse en la ruta donde se haya copiado el ejecutable `vbn` (por defecto, en `/home/root/`).

### Modo "default"
Modo de ejecución predeterminada, con setup real de vuelo:

```
./vbn /run/media/nvme0n1p1/RSBvoc.txt /media/sd-mmcblk0p2/imx296+88-590-0107.yaml can0 1000000 1006 192.168.1.251 10 256
```

### Modo "prerecords"

Modo de ejecución que carga los datos de vuelo desde un fichero, en lugar de capturar imágenes del sensor y datos de GPS de veronte (con fines de desarrollo y depuración, principalmente):

```
./vbn /run/media/nvme0n1p1/RSBvoc.txt /media/sd-mmcblk0p2/imx296+88-590-0107.yaml can0 1000000 1006 192.168.1.251 10 256 /media/sd-mmcblk0p2/datasets/00000_02_07_2025/records.txt
```

### Modo "record"

Modo de grabación, con setup real de vuelo, que permite grabar los datos de una prueba de vuelo para, posteriormente, poder reproducirlos y llevar a cabo pruebas con el modo "prerecords", descrito anteriormente:

```
./vbn /run/media/nvme0n1p1/RSBvoc.txt /media/sd-mmcblk0p2/imx296+88-590-0107.yaml can0 1000000 1006 192.168.1.251 10 256 record
```

## 4.1. Viewer deployment
El comando para ejecutar el visualizador en una máquina o PC local es el siguiente, modificando la IP final por la de la placa donde se esté ejecutando el VBN:

```
./viewer /workspace/items/sw_gnssdenied/items/sw_orbslam/Vocabulary/ORBvoc.txt /workspace/ros_wrapper_ws/src/orb_slam3/scripts/imx296+88-590.yaml 192.168.1.162
```

## 4.2. Remote debugging

Para depurar el software por red con vscode, en caso de ejecución sobre la placa, se puede utilizar gdbserver. 

- Desde la placa, con el software actualizado y un petalinux en ejecución, lanzar la instrucción "**gdbserver localhost:1234 ./vbn ...**". 

- Desde VSCode, en la pestaña depuración (*Debug*), seleccionar la opción Remote AXU o Remote VBN. Si es necesario, ajustar la IP del fichero `.json` para que se corresponda con la placa a trabajar.
