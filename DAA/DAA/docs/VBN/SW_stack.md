# VBN: SW_stack
- [VBN: SW\_stack](#vbn-sw_stack)
  - [Descripción](#descripción)
  - [Herramientas de desarrollo](#herramientas-de-desarrollo)
  - [Aplicación de usuario](#aplicación-de-usuario)
      - [Streamimg de video:](#streamimg-de-video)
  - [Drivers de IPs](#drivers-de-ips)
  - [Petalinux](#petalinux)



## Descripción

El Sw de la plataforma esta basado en el SO Petalinux.
Consta de tres capas:

- La aplicación de usuario (p. ej: gnss_denied) y librerías de alto nivel.
- Los drivers para manejo de los IPs implementados en la parte FPGA.
- El sistema operativo Petalinux que incluye diversos drivers para manejo de dispositivos (CAN, UART, dma, etc...).

![Sw_detalles](./img/VBN_Sw_detallada.png)

## [Herramientas de desarrollo](./sw_env_setup.md)

## Aplicación de usuario

#### Streamimg de video:

## Drivers de IPs

Se han utilizado los drivers proporcionados por Xilinx para el manejo de los IPs. Para los custom IPs se utiliza el driver genérico AXILite que proporciona la herramienta Vitis_HLS. 

Los parámetros de configuración de los pipelines de la FPGA son los siguientes: 

<table><tr><th colspan="1" valign="top"><b>pipe</b></th><th colspan="1" valign="top"><b>etapa</b></th><th colspan="1" valign="top"><b>parámetro</b></th><th colspan="1" valign="top"><b>#dat</b></th><th colspan="1" valign="top"><b>bytes</b></th><th colspan="1" valign="top"><b>type</b></th><th colspan="1" valign="top"><b>default</b></th><th colspan="1" valign="top"><b>comentario</b></th></tr>
<tr><td colspan="1" rowspan="27"><p><b>/ ACONDICIONAMIENTO</b></p><p><b>CAPTURA</b></p></td><td colspan="1">cámara</td><td colspan="1">Registros conf.</td><td colspan="1">n</td><td colspan="1">n*4</td><td colspan="1">uint32</td><td colspan="1">-</td><td colspan="1"><p>Configuración cámara</p><p>crop 1280x960</p></td></tr>
<tr><td colspan="1">MIPI_Rx</td><td colspan="1">-</td><td colspan="1"></td><td colspan="1">-</td><td colspan="1"></td><td colspan="1"></td><td colspan="1">-</td></tr>
<tr><td colspan="1" rowspan="3"><p>Demosaic</p><p>RAW->RGB</p></td><td colspan="1">active  width</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1280</td><td colspan="1">ancho  imagen</td></tr>
<tr><td colspan="1">active high</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint32</td><td colspan="1">960</td><td colspan="1">alto  imagen</td></tr>
<tr><td colspan="1">Bayer phase</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">0</td><td colspan="1">inicio del grid  Bayer</td></tr>
<tr><td colspan="1" rowspan="6">Gamma</td><td colspan="1">active  width</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1280</td><td colspan="1"></td></tr>
<tr><td colspan="1">active high</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">960</td><td colspan="1"></td></tr>
<tr><td colspan="1">video format</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">0</td><td colspan="1">espacio de color del video de entrada</td></tr>
<tr><td colspan="1">LUT red</td><td colspan="1">1x512</td><td colspan="1">2048</td><td colspan="1">int32</td><td colspan="1">(*)</td><td colspan="1">tabla coeficientes</td></tr>
<tr><td colspan="1">LUT green</td><td colspan="1">1x512</td><td colspan="1">2048</td><td colspan="1">int32</td><td colspan="1">(*)</td><td colspan="1">tabla coeficientes</td></tr>
<tr><td colspan="1">LUT blue</td><td colspan="1">1x512</td><td colspan="1">2048</td><td colspan="1">int32</td><td colspan="1">(*)</td><td colspan="1">tabla coeficientes</td></tr>
<tr><td colspan="1" rowspan="8"><p>Color conv.</p><p>RGB->YUV</p></td><td colspan="1">width</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1280</td><td colspan="1">ancho  imagen</td></tr>
<tr><td colspan="1">heigh</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">960</td><td colspan="1">alto  imagen</td></tr>
<tr><td colspan="1">input video</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">0</td><td colspan="1">formato video entrada</td></tr>
<tr><td colspan="1">output video</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">1</td><td colspan="1">formato video salida</td></tr>
<tr><td colspan="1">coeficientes</td><td colspan="1">3x3</td><td colspan="1">36</td><td colspan="1">int32</td><td colspan="1">(**)</td><td colspan="1">` `conversión RGB -> YUV 4:4:4</td></tr>
<tr><td colspan="1">offsets</td><td colspan="1">3x1</td><td colspan="1">12</td><td colspan="1">int32</td><td colspan="1">(**)</td><td colspan="1">offsets conversión</td></tr>
<tr><td colspan="1">clap mín</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">0</td><td colspan="1">valor  recorte  mín</td></tr>
<tr><td colspan="1">clap máx</td><td colspan="1">1</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">255</td><td colspan="1">valor recorte máx</td></tr>
<tr><td colspan="1" rowspan="4"><p>Escalado</p><p>->640x480</p></td><td colspan="1">width</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1280</td><td colspan="1">ancho  imagen</td></tr>
<tr><td colspan="1">heigh</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">960</td><td colspan="1">alto imagen</td></tr>
<tr><td colspan="1">scale</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">2</td><td colspan="1">escala</td></tr>
<tr><td colspan="1">scale_inv</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1/2</td><td colspan="1">1/escala</td></tr>
<tr><td colspan="1" rowspan="4">VDMA</td><td colspan="1">s2mm_vsize</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">640</td><td colspan="1">ancho imagen</td></tr>
<tr><td colspan="1">s2mm_hsize</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">480</td><td colspan="1">alto  imagen</td></tr>
<tr><td colspan="1">s2mm_add</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">(***)</td><td colspan="1">dirección inicio frmbuff</td></tr>
<tr><td colspan="1">s2mm_stride</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1xhsize</td><td colspan="1">distancia en bytes entre el inicio de  dos lineas</td></tr>
<tr><td colspan="1" rowspan="11"><b>COPRO. ORB</b></td><td colspan="1" rowspan="5"><p>Rsz</p><p>FAST</p><p>BRIEF</p></td><td colspan="1">width</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">640</td><td colspan="1">ancho  imagen</td></tr>
<tr><td colspan="1">heigh</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">480</td><td colspan="1">alto imagen</td></tr>
<tr><td colspan="1">scale</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1</td><td colspan="1">escala</td></tr>
<tr><td colspan="1">scale_inv</td><td colspan="1">1</td><td colspan="1">2</td><td colspan="1">uint16</td><td colspan="1">1</td><td colspan="1">1/escala</td></tr>
<tr><td colspan="1">TH</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">40</td><td colspan="1">umbral FAST</td></tr>
<tr><td colspan="1" rowspan="6">DMA</td><td colspan="1">mm2s_SA</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">(***)</td><td colspan="1">dirección fuente</td></tr>
<tr><td colspan="1">mm2s_SA_MSB</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">(***)</td><td colspan="1">MSB de dir fuente</td></tr>
<tr><td colspan="1">mm2s_LENGTH</td><td colspan="1">wxh</td><td colspan="1">1</td><td colspan="1">uint8</td><td colspan="1">640x480</td><td colspan="1">longitud de la transf (bytes)</td></tr>
<tr><td colspan="1">s2mm_DA</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">(***)</td><td colspan="1">dirección destino</td></tr>
<tr><td colspan="1">s2mm_DA_MSB</td><td colspan="1">1</td><td colspan="1">4</td><td colspan="1">uint32</td><td colspan="1">(***)</td><td colspan="1">MSB de dir destino</td></tr>
<tr><td colspan="1">s2mm_LENGTH</td><td colspan="1">4096</td><td colspan="1">struc</td><td colspan="1">uint128</td><td colspan="1">(+)</td><td colspan="1">longitud de la transf (bytes)</td></tr>
</table>

(\*) los coeficientes se calculan mediante una función del driver gamma\_calc(valor\_gamma), se pueden sustituir por un solo parámetro: valor\_gamma

(\*\*) cableados en el driver

(\*\*\*) puntero a la dirección física del framebuffer/buffer de datos

(+) structura de datos, distintos tipos de datos (coordenadas, descriptor, score)




## Petalinux
