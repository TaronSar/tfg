# HOW TO LOAD BITSTREAM

After start up the openocd server with the provided configuration, connect with telnet:
```
$ telnet localhost 4444
```

And run the following command:
```
$ pld load device_name.tap bitsteam.bit
```
The device name (device_name.tap) are provided by the following command:

```
$ pld devices
#0: uscale.pld (driver: virtex2)
```
The device name is uscale.pld.



# HOW TO LOAD SOFTWARE

Using gdb the port 3333 is open to connections. Using the following command the software file should run:

```
$ file app.elf
$ load
$ continue

```