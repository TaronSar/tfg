# CAN FD 2 Click - Jetson Nano

Este proyecto configura automáticamente el transceiver **CAN FD 2 Click / TLE9255W** en una Jetson Nano.

El transceiver se configura por SPI y se pone en **Normal Operation Mode**, permitiendo convertir las señales lógicas `CAN_TX` / `CAN_RX` de la Jetson a las señales diferenciales del bus CAN: `CAN_H` / `CAN_L`.

---

## Archivos necesarios

Los scripts deben estar instalados en las siguientes rutas:

```bash
/usr/local/sbin/canfd2_init.py
/usr/local/sbin/setup_canfd2.sh
/etc/systemd/system/canfd2.service
```

## Permisos recomendados

```bash
sudo chmod +x /usr/local/sbin/canfd2_init.py
sudo chmod +x /usr/local/sbin/setup_canfd2.sh
```

## Servicio systemd

El servicio encargado de inicializar el transceiver es:

```bash
canfd2.service
```

Este servicio:

- Configura el TLE9255W por SPI.
- Pone el transceiver en modo Normal Operation.
- Carga los módulos CAN necesarios del kernel.
- Configura y levanta la interfaz can0.
- Termina correctamente.

Como es un servicio de tipo oneshot, es normal que su estado sea:

```text
active (exited)
```

Eso significa que se ha ejecutado correctamente y ha terminado.

## Instalación / actualización del servicio

Después de copiar o modificar el archivo:

```bash
/etc/systemd/system/canfd2.service
```

hay que recargar systemd:

```bash
sudo systemctl daemon-reload
```

Para habilitar el servicio en el arranque:

```bash
sudo systemctl enable canfd2.service
```

Para ejecutarlo manualmente:

```bash
sudo systemctl start canfd2.service
```

Para reiniciarlo:

```bash
sudo systemctl restart canfd2.service
```

## Comandos útiles

Recargar systemd después de modificar el servicio:

```bash
sudo systemctl daemon-reload
```

Habilitar el servicio en el arranque:

```bash
sudo systemctl enable canfd2.service
```

Arrancar el servicio manualmente:

```bash
sudo systemctl start canfd2.service
```

Reiniciar el servicio:

```bash
sudo systemctl restart canfd2.service
```

Comprobar estado:

```bash
systemctl status canfd2.service
```

Un estado correcto sería algo similar a:

```text
Active: active (exited)
```

Ver logs del arranque actual:

```bash
journalctl -u canfd2.service -b
```

Ver logs en tiempo real:

```bash
journalctl -u canfd2.service -f
```

## Verificación de la interfaz CAN

Comprobar que can0 existe y está levantada:

```bash
ip -details link show can0
```

Prueba de recepción:

```bash
candump can0
```

Prueba de envío:

```bash
cansend can0 123#DEADBEEF
```

## Notas importantes

En esta Jetson Nano, la comunicación SPI con el TLE9255W funciona usando:

```text
SPI bus:    0
SPI device: 0
SPI mode:   0
SPI speed:  1 MHz
```

Las lecturas por MISO llegan desplazadas 1 bit a la derecha, por lo que el script canfd2_init.py corrige las lecturas aplicando:

```text
(result[1] << 1) & 0xFF
```

La escritura por SPI funciona normalmente.

La secuencia usada para poner el transceiver en modo normal es:

```text
MODE_CTRL = STANDBY
MODE_CTRL = NORMAL_OPERATION
```

Es decir:

```text
0x01 = 0x02
0x01 = 0x08
```

## Rutas finales

```bash
/usr/local/sbin/canfd2_init.py
/usr/local/sbin/setup_canfd2.sh
/etc/systemd/system/canfd2.service
```