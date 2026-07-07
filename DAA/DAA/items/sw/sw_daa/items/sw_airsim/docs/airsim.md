# AirSim — Documentación de funcionamiento

## Índice

1. [Descripción general](#descripción-general)
2. [Configuración](#configuración)
   - [settings.json principal](#settingsjson-principal)
   - [Vehículo (uav_veronte.json)](#vehículo-uav_verontejson)
   - [Cambio de vehículos en Unreal Engine](#cambio-vehiculos-unreal)
   - [Importar Assets Comprados en Unreal Engine](#importar-compras)
   - [Estructura de carpetas](#estructura-de-carpetas)
3. [Modelo físico del dron](#modelo-físico-del-dron)
   - [Masa e inercia](#masa-e-inercia)
   - [Motores y RVARs](#motores-y-rvars)
4. [Integración con Unreal Engine](#integración-con-unreal-engine)
   - [Modificación del código base de AirSim](#modificacion-codigo-airsim)
   - [Plugin AirSim](#plugin-airsim)
   - [Empaquetado del proyecto Unreal Engine](#empaquetado-proyecto-unreal)
   - [Blueprints disponibles](#blueprints-disponibles)
   - [Simulate Physics](#simulate-physics)
5. [Bridge AirSim–Veronte](#bridge-airsim-veronte)
   - [Flujo de datos](#flujo-de-datos)
   - [Sensores publicados](#sensores-publicados)
   - [Escritura de actuadores](#escritura-de-actuadores)
6. [Debug y herramientas](#debug-y-herramientas)
   - [verify_imu.py](#verify_imupy)
   - [entrypoint_bounding_box_simulator.sh](#entrypoint-bounding-box-simulator)
   - [colors_table.json](#colors-table)
   - [airsim_assets_manager.py](#airsim-assets-manager)
   - [airsim_simulation_runner.py](#airsim-simulation-runner)
   - [track_waypoints.py](#track-waypoints)
   - [apply_simulation_config.py](#apply_simulation_configpy)
   - [save_simulation_config.py](#save_simulation_configpy)
   - [simulation_config.sh](#simulation-config)
   - [build_trajectories.py](#build-trajectoriespy)
   - [convert_images_to_video.sh](#convert_images_to_videosh)
   - [build_and_launch_trajectories.sh](#build_and_launch_trajectoriessh)
   - [debug_udp.py](#debug-udp)
   - [verify_sensors.py](#verify-sensorspy)
   - [LAUNCH](#launch)
7. [Problemas conocidos](#problemas-conocidos)
8. [Referencias](#referencias)

---

## Descripción general
AirSim es el simulador utilizado para tareas de visión (DAA/PAT/KAI, etc.) en sustitución de XPlane. Utiliza Unreal Engine como motor de renderizado para crear los modelos de mundos, vehículos, etc. El repositorio público de AirSim ofrece el controlador PX4 (el que se utilizó en el Proyecto Colibrí) y también ofrece su propio controlador SimpleFlight. En este ítem se ha añadido el controlador Veronte utilizado mediante PyVeronte. Se está desarrollando esta comunicación mediante VCP para poder ser utilizada tanto en SIL como en HIL, igual que se hace hoy en día con XPlane.


## Configuración

### settings.json principal
La configuración que recibe AirSim se encuentra en `settings.json`. Para facilitar su uso, desde Catec se definió la carpeta `settings` y, en ella, un archivo llamado `setup.py`. Este genera `settings.json` a partir de las definiciones del resto de archivos JSON de esta carpeta. De esta manera, se pueden modificar: `uav_veronte.json`, `dynamics.json`, `static.json` y `config_simulation.json`, definiendo campos específicos en cada uno de ellos.

Llevando este desarrollo más adelante, se ha modificado el setup de la siguiente manera:
- Se ha creado un JSON genérico para cada simulación, de manera que si se quiere guardar el setup actual, se copien los datos de todos los ficheros anteriores en uno solo con un nombre determinado. De esta manera, en la carpeta sw_airsim/items/sim/ se tienen todas las configuraciones creadas con las que se puede ejecutar AirSim. Por un lado, se tiene un JSON que define parámetros como configuración de la simulación, del vehículo, de los objetos en el mundo, etc. Y por otro lado un YAML con el mismo nombre que define las trayectorias que debe seguir el dron, que serán la entrada al autopiloto.
- Para tratar este proceso se crea `scripts/simulation_config.sh`: si se le llama con el argumento `./simulation_config.sh apply {nombre_simulacion}` se aplicará la configuración definida en `sw_airsim/items/sim/{nombre_simulacion}.json` a los archivos JSON de la carpeta `settings`, es decir, será la próxima simulación que se ejecute. En cambio, si se le llama con el argumento `./simulation_config.sh save {nombre_simulacion}` se guardará la configuración definida en los archivos JSON de la carpeta `settings` en el archivo `sw_airsim/items/sim/{nombre_simulacion}.json`.

### Vehículo (uav_veronte.json)
Se han añadido nuevos campos al vehículo aplicados a la simulación:
- Mass: la masa del dron.
- RotorCount: número de motores del dron.
- RotorRVARs: vector de RVARs asociadas a los motores.
- PawnPath: ruta al Blueprint que se utilizará como vehículo.
<!--
Ruta: items/sw/sw_daa/items/sw_airsim/code/settings/internal/uav_veronte.json
Campos relevantes: Mass, RotorCount, RotorRVARs, PawnPath.
-->

### Cambio de vehículos en Unreal Engine
Los modelos de los vehículos se crean en XPlane ya que es el simulador que se utiliza comúnmente en Embention para las simulaciones. Desde XPlane es posible exportar en formato STL (anotar que aunque se pueda exportar en OBJ que es un formato importable en Unreal Engine, no funciona correctamente ya que este OBJ exportado no contiene toda la información del modelo).

El formato STL no se puede importar en Unreal Engine, pero sí en Blender. Se importa el modelo STL en Blender. Se elige Shade Smooth sobre el elemento. Se pulsa la llave inglesa de color azul, Add Modifier, en Normal se selecciona Smooth by Angle. A continuación, se separan las hélices de la aeronave. Se centran correctamente en los ejes de coordenadas (parte muy importante, si no no rotarán en el sentido correcto en la simulación). Opción: definir origen -> geometría al origen. Cuando está centrado en el eje, se debe observar la posición y rotación en 0.0.

Desde Blender se exporta cada una de las piezas por separado, en formato FBX. Al exportar: seleccionar la opción de exportar únicamente la pieza seleccionada, y desmarcar Skeletal Mesh. Desde UE4, importar FBX.

Tras importar, se abre el editor del objeto y en Detalles, en LOD 0, se selecciona `Recompute Normals y Tangents` y se desselecciona `Use MikkTSpace Tangent Space`. Además, se le da una textura al objeto. Se importa el dron y todas las hélices. Se crea un Blueprint y se añaden los componentes en él. Se construye el dron en el espacio y se define el Blueprint de movimiento (observar la estructura en los otros Blueprints ya creados).

### Importar Assets Comprados en Unreal Engine
Los assets se compran en la página oficial de Unreal Engine. Algunos se descargan directamente en FBX, por lo que solo hay que importarlos, pero otros se guardan en la biblioteca de FAB. Se deben descargar desde Epic Games Launcher. Este launcher no está disponible en UE4 para Linux; está disponible a partir de UE5 o en Windows. Por ello, se descargó Epic Games Launcher en el portátil Windows del equipo de Visión y se accedió a los assets comprados. Se crea un proyecto vacío en el que se importan todos los assets. El proyecto se sube a Drive y se descarga en el portátil Windows; de esta manera ya se tiene acceso a todos los assets comprados, ya que se quedan guardados en la carpeta Contents y se pueden copiar y pegar entre proyectos fácilmente.

### Estructura de carpetas
En `sw_airsim` se tiene `code`, `items` y `docs`.
- `code`:
  - `airsim`: carpeta con el código base de AirSim que ha sufrido modificaciones. No es exactamente el mismo que se puede encontrar en la página de GitHub de AirSim; se han añadido opciones de Veronte.
  - `Dockerfiles`: scripts de definición de los dockers así como scripts que utilizan los contenedores para el control de la simulación.
  - `DockerSavedImages`: imágenes aportadas por catec a partir de las cuales se construyen los dockers con los que se inicia la simulación.
  - `records`: carpeta donde se guardan las imágenes cuando se activa la opción de grabar en AirSim.
  - `scripts`: scripts para lanzar los procesos en los contenedores así como otros scripts de diversas utilidades.
  - `settings`: carpeta con las configuraciones de la simulación.
  - `simulator`: carpeta donde se guardan los mundos que se utilizarán en la simulación.
  - `test`: carpeta con tests utilizados para debug.
  - `video_records`: carpeta donde se guardan los vídeos que se pueden generar a partir de las escenas grabadas (en PNG) en la carpeta `records`.
  - Incluye los ficheros principales para iniciar AirSim: setup, launch, etc.
- `docs`: documentos informativos que explican el proceso.
- `items`:
  - `sim`:
    - Incluye los JSON y YAML que definen las configuraciones de las simulaciones guardadas, para poder replicarlas en caso de necesidad.
    - Carpetas synthetic_data_{sim} donde se guardan los datos sintéticos generados por la simulación.
  - `sim_Template`: configuración por defecto que dejó catec. Hay muchas cosas que se han borrado de la carpeta `code` porque no se utilizan actualmente como los markers estáticos así como otras funcionalidades. Pero se guarda en esta carpeta por si pueden servir en futuros desarrollos.


## Modelo físico del dron

### Masa e inercia

<!--
La masa debe configurarse SOLO en uav_veronte.json ("Mass": <kg>).
NO activar Simulate Physics en el Blueprint de Unreal: AirSim gestiona su
propia física internamente. Activarlo genera conflicto entre dos motores de
física y hace el dron inestable.

Si se necesita inercia personalizada, debe aplicarse vía C++ en AirLib
(FlyingPawn.cpp) después de BeginPlay, usando la API PhysX.
-->

### Motores y RVARs
El código de airsim consta de una carpeta para cada controlador. Se ha añadido una carpeta para Veronte (cuando se defina el vehículo en settings como Veronte, se utilizará este código). Se ha añadido:
- Nuevo método moveByVerontePWMsAsync. El método que define AirSim solo deja enviar comandos PWM a 4 motores. En el caso de Embention, se utilizan drones que muchas veces tienen más de 4 motores. Por ello se ha creado un nuevo método que permite enviar un vector de motores (este número debe ser definido en las nuevas opciones de settings).
- Definición de masa según el archivo settings.
<!--
RotorCount: número de rotores.
RotorRVARs: IDs de los canales de actuador en Veronte (1700–170N).
-->

## Integración con Unreal Engine
### Modificación del código base de AirSim
En el caso de necesitar modificar el código base de AirSim, ubicado en la carpeta `sw_airsim/code/airsim/`, se tendrá que compilar el código así como cargarlo en los contenedores. La parte de compilación del código de AirSim se explica en el Apartado [siguiente](#plugin-airsim). Una vez compilado, se debe introducir en el docker para que cuando se ejecute el launcher de AirSim, sea este código el que se ejecute dentro del contenedor.

El contenedor se construye a partir de la imagen compilada por Catec, es decir, utiliza la versión que dejaron compilada. Por ello, se ha desarrollado un script que, a partir de esta imagen, sustituye el compilado de AirSim y lo actualiza. Simplemente se debe ejecutar `./sw_airsim/code/Dockerfiles/base/airsim_update.sh` para que se actualice. En ese momento, cuando se ejecute el launch, el código ejecutado de AirSim será el que había en la carpeta `code/airsim/` en el momento de ejecutar el update.

### Plugin AirSim
Importante: cuando se realizan cambios en el código de AirSim, se debe volver a copiar el Plugin en Unreal Engine. Es decir:
- Paso 1: se modifica código base de AirSim en sw_airsim/code/airsim/.
- Paso 2: compilación de este código.
  - Paso 2.1: limpieza de permisos corporativos. Si el sistema bloquea archivos antiguos de Docker/Sudo, recupera la propiedad de la carpeta (si no se hace, build pretende borrarlas y solicita permisos en bucle): `sudo chown -R {user}@ad.embention.com ~/DAA/items/sw/sw_daa/items/sw_airsim/code/airsim`.
  - Paso 2.2: limpieza de caché de CMake: 
    - `cd ~/DAA/items/sw/sw_daa/items/sw_airsim/code/airsim`
    - `sudo rm -rf build_release/ build_debug/ AirLib/lib/ AirLib/deps/rpclib/lib/`
  - Paso 2.3: compilación (utiliza Clang 18 por defecto): `./build.sh`.
- Paso 3: compatibilidad en Unreal Engine.
  - Paso 3.1: copiar el plugin al proyecto.
    - `rm -rf /home/unreal_projects/{proyecto}/Plugins/AirSim`
    - `cp -r Unreal/Plugins/AirSim /home/unreal_projects/{proyecto}/Plugins/`
  - Paso 3.2: aplicar objcopy al archivo .a. Forzar el reemplazo del símbolo moderno por el clásico compatible con Unreal Engine: `objcopy --redefine-sym __isoc23_strtol=strtol /home/unreal_projects/{proyecto}/Plugins/AirSim/Source/AirLib/deps/rpclib/lib/librpc.a`
- Paso 4: Compilación en Unreal.
  - Paso 4.1: limpieza drástica de caché de Unreal Engine. Se borran los archivos temporales del mapa para obligarle a leer el nuevo código y el binario parcheado.
    - `cd /home/unreal_projects/{proyecto}/`
    - `rm -rf Binaries/ Intermediate/ Saved/`
  - Paso 4.2: compilación del editor. Se va a la raíz del motor Unreal y se compila usando el script de Linux con todos sus argumentos.
    - `cd ~/Git-projects/UnrealEngine`
    - `./Engine/Build/BatchFiles/Linux/Build.sh {proyecto}Editor Linux Development -project="/home/unreal_projects/{proyecto}/{proyecto}.uproject"`
- Paso 5: lanzamiento. Una vez que aparece el éxito del paso [9/9], abre el editor.

<!--
Versión, fork, ruta en el proyecto Unreal.
-->

### Empaquetado del proyecto Unreal Engine
Para lanzar la simulación con el proyecto realizado en Unreal Engine, los pasos son los siguientes:
- Paso 1: empaquetar el proyecto de Unreal Engine. 
  - En la propia aplicación, en el menú desplegable aparece la opción de empaquetar. Pero es probable que el ordenador no sea capaz de empaquetar con esta opción y se apague.
  - Para poder empaquetar, se puede utilizar un script externo (de manera que no se tenga el editor abierto para compilar), así como cerrar otras aplicaciones que consuman como VS code o Chrome.

```bash
#!/bin/bash
# Ajusta las rutas a tu instalación real
set -e # Detiene el script si un comando falla
# Mata el script y a TODOS sus procesos hijos si pulsas Ctrl+C
trap "kill 0" INT

ENGINE_PATH="/home/{user}/Git-projects/UnrealEngine/Engine/Build/BatchFiles/RunUAT.sh"
PROJECT_PATH="/home/unreal_projects/{proyecto}/{proyecto}.uproject"
ARCHIVE_PATH="/home/unreal_projects/{proyecto}/Binaries/Linux"

$ENGINE_PATH BuildCookRun \
  -project="$PROJECT_PATH" \
  -noP4 -platform=Linux -clientconfig=Development \
  -cook -NumCookersToSpawn=8 -allmaps -build -stage -pak -archive \
  -archivedirectory="$ARCHIVE_PATH"
```

### Blueprints disponibles
A manera de desarrollo inicial, los blueprints disponibles (que se han utilizado) son:
- BP_FlyingPawn: es el dron que se tenía de catec (proyecto Colibrí) y que se ha estado utilizando para pruebas.
- BP_MantaVTOL: dron Manta.
- BP_MantaVTOL_6motores: dron Manta con más motores para probar el control con más de 5 motores.


Estos blueprints que definen el dron (actor de la escena) se encuentran en la carpeta: `Plugins/AirSim/Content/Blueprints/`. Esto es importante porque significa que cuando se modifique el código fuente de AirSim en la carpeta `sw_airsim/code/airsim/`, como se ha explicado antes, la carpeta anterior se actualizará. Por lo que cuando se desarrolle un Blueprint nuevo en un proyecto, para que se quede guardado es importante copiar el Blueprint a la carpeta `sw_airsim/code/airsim/Unreal/Plugins/AirSim/Content/Blueprints/` para que se quede guardado. De manera que si posteriormente se modifica el código base y actualiza el Plugin del proyecto, el nuevo Blueprint no se elimine. Además, esto es una forma también de poder guardar todos estos Blueprints en GitHub y que sean reutilizables por el equipo, ya que los proyectos de Unreal no se suben a GitHub (si no a Drive y se está valorando si al NAS de visión).
<!--
Lista de pawns disponibles en el proyecto empaquetado y sus rutas UAsset.
-->

### Simulate Physics
Actualmente, el dron no realiza un vuelo con los comandos de Veronte, a pesar de responder a sus directrices. Tras comentarlo con PDI, surgen dos opciones para justificar este fallo:
- Latencia de la comunicación. Se solucionará con el desarrollo de APPs ya que será la misma comunicación que se hace actualmente con XPlane.
- Falta de simulación de físicas. Es decir, en XPlane se define la masa, el centro de gravedad y la matriz de inercia. En el caso de AirSim, el código base podría controlar estos aspectos. Desde Unreal Engine no es posible cambiarlo: hay parámetros comentados que no aparecen y, además, si se añaden, estos chocan con la física definida por AirSim y el dron se vuelve altamente inestable. Es por ello que se va a comenzar con la modificación del código de AirSim para poder controlar estas físicas a través de `settings.json` (modificando el código base de AirSim).
<!--
⚠️ No activar en el pawn raíz cuando se usa AirSim multirotor.
AirSim aplica fuerzas directamente sobre el componente raíz; si Unreal
también simula física, ambos motores se contradicen en cada frame.
-->

## Bridge AirSim–Veronte

### Flujo de datos
El bridge funciona como nodo ROS con un ciclo de control y dos pipelines complementarios:

- Input path: AirSim -> AirSimReader -> VeronteSILWriter -> PyVeronte SIL.
- Output path: PyVeronte SIL -> VeronteSILReader -> AirSimWriter -> AirSim.

Secuencia de cada iteración:
1. AirSim publica sensores en topics ROS (IMU, GNSS, barómetro, magnetómetro y odometría).
2. AirSimReader recoge los topics, aplica lock y construye un SensorSnapshot consistente.
3. VeronteSILWriter serializa el snapshot completo en PyVeronte:
  - IMU: writeImu
  - STP/baro: writeStp + RVARs de presión
  - Qinf/dinámica: writeQinf
  - MAG: writeMag (+ RVARs de campo cuando aplica)
  - GNSS (2): writeGnssRaw
  - RNED: writeRnedRaw
  - GPS time: writeGnssTimeRaw
4. El bridge avanza Veronte SIL con step(dt) (incluyendo actualización de RVAR de dt para sincronizar tiempo simulado).
5. VeronteSILReader lee outputs de control de Veronte:
  - RVARs de motores.
  - Actitud estimada.
6. AirSimWriter transforma los outputs de Veronte y los aplica a AirSim:
  - Para flujo Veronte extendido (N motores): moveByVerontePWMsAsync.

Notas de sincronización:

- El bridge es el orquestador temporal del lazo; después de cada escritura de mandos se avanza el reloj de AirSim para mantener consistencia entre física y control.
- Tras un reset de Veronte, se reatacha la instancia del reader al nuevo objeto PyVeronte para no romper el output path.

### Sensores publicados
Los sensores publicados por AirSim son:
- Barómetro.
- IMU.
- GPS.
- Magnetómetro.
- LiDAR.

Frecuencia de muestreo vía ROS topics:
```text
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:501 - Sensor                                   Poll Rate (Hz)  Update Rate (Hz)   Samples/s   
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:502 - ------------------------------------------------------------------------------------------
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:517 - Barometer_HSC                            47.7            47.7               47.7        
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:517 - Imu_ADIS                                 47.7            47.7               47.7        
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:517 - Gps_1                                    47.7            47.7               47.7        
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:517 - Magnetometer_LIS                         47.7            47.7               47.7        
2026-05-27 08:14:09.473 | INFO     | __main__:run_ros_verification:517 - Lidar_1                                  4.8             4.8                4.8         
```

Frecuencia de muestreo vía AirSim API:
```text
2026-05-27 08:09:57.893 | INFO     | __main__:run_api_verification:416 - Sensor                                   Poll Rate (Hz)  Update Rate (Hz)   Samples/s   
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:417 - ------------------------------------------------------------------------------------------
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:419 - Barometer (Barometer_HSC)                547.4           22.8               22.8        
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:419 - IMU (Imu_ADIS)                           547.4           318.7              318.7       
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:419 - GPS (Gps_1)                              547.4           22.8               22.8        
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:419 - Magnetometer (Magnetometer_LIS)          547.4           22.8               22.8        
2026-05-27 08:09:57.894 | INFO     | __main__:run_api_verification:419 - LiDAR (Lidar_1)                          547.4           4.8                4.8    
```

### Escritura de actuadores

Con los cambios actuales, la escritura de actuadores del bridge se realiza con el método extendido de AirSim para Veronte, permitiendo controlar N motores sin limitarse a 4 canales.

Flujo de actuadores:

1. VeronteSILReader lee los canales de actuador desde RVARs configuradas (ajustable por configuración en settings.json).
2. Se construye un VeronteOutputSnapshot con:
  - motor_outputs: vector de salidas de motor (longitud N).
  - roll, pitch, yaw y throttle para telemetría/diagnóstico (se puede enviar estos comandos directos a AirSim desde Veronte. Actualmente no está activado pero se ha dejado comentado por si surge la necesidad de debugear o comparar ambos controles).
3. AirSimWriter valida que el snapshot tenga al menos los motores requeridos por el mapa de índices configurado.
4. AirSimWriter envía directamente el vector de motores a AirSim mediante moveByVerontePWMsAsync(pwm_values, dt).
5. Tras enviar los actuadores, el bridge avanza el reloj de simulación con simStep(dt) para mantener sincronía temporal.

Diferencia respecto al método clásico:

- moveByMotorPWMsAsync (clásico AirSim) acepta exactamente 4 motores en orden fijo.
- moveByVerontePWMsAsync (extensión Embention) acepta un vector de tamaño N y habilita configuraciones de 5, 6 o más motores.

Notas de implementación:

- En start() y stop() se envía un vector de ceros para limpiar el latch de salida directa y evitar residuos de mando entre ejecuciones.
- El método alternativo por actitud (roll/pitch/yaw/throttle) se mantiene como fallback de depuración, pero el camino principal de control es por vector de motores.
- El orden de envío de los motores debe ser el mismo que el de definición en Unreal Engine. Es decir, en el Blueprint del dron en Unreal Engine se define cada una de las hélices a las que se quiere aplicar movimiento como: prop0, prop1, prop2, etc. El orden de envío de PWMs debe ser el mismo. Si prop0 es la hélice trasera izquierda, el primer valor de PWM en el vector debe ser el suyo.
- PWM debe estar en el rango [0, 1].
- En la escena de Unreal Engine no debe aparecer el dron. Lo spawnea automáticamente AirSim al indicarle el Blueprint.

## Debug y herramientas

### Verify_imu.py
- Ruta: sw_airsim/code/test/verify_imu.py.

Fue un código diseñado junto a PDI para testear el correcto funcionamiento de la IMU. Esta función se debe llamar desde VeronteSILWriter. En lugar de enviar los datos obtenidos de AirSim para la IMU hacia Veronte, se utiliza este método de verificación para enviar datos de ángulos conocidos (datos de IMU sintéticos). En Veronte OPS, se podrá observar el giro con el elemento `Attitude` que debe obtener ese ángulo. De esta manera se testea que los datos de IMU se envían correctamente a Veronte.

Para activar esta opción, se debe modificar la variable `USE_IMU_DEBUG_WRITER` a True, en el archivo `airsim_veronte_bridge_config.py`.

### entrypoint_bounding_box_simulator.sh
Se ha creado un script que se ejecuta automáticamente cuando se lanza la simulación con la opción `--bounding_box_simulation`. Este hace que se dibuje un bounding box sobre los obstáculos que aparecen en la escena, actúa como un detector y permite obtener los datos necesarios para la generación de datos sintéticos:
- Imágenes RGB.
- Imágenes en profundidad y segmentadas.
- JSON con la información de los bounding boxes en el formato COCO requerido para los entrenamientos.

Además, si en lugar de utilizar esta opción se utiliza `--store_bbox`, se guardarán también las imágenes RGB con el bounding box dibujado. Esto es útil para depurar el correcto funcionamiento del script.

Llama a segmentation_dataset_builder.py.

### colors_table.json
Para la obtención del bounding box alrededor del objeto, se realiza una segmentación. Se asigna un ID a cada objeto y se configura la cámara de manera que las imágenes segmentadas obtenidas, observen la escena de un único color y los objetos con el color relacionado a su ID asignado. Esto permite obtener las posiciones exactas de los objetos en todo momento. El fichero `colors_table.json` relaciona los IDs con colores RGB. De manera que se pueda relacionar que si un objeto tiene asignado el ID 20, se debe buscar el color (r, g, b) en la escena para detectarlo.

Ojo: AirSim ofrece una tabla de relaciones entre ID y colores en la imagen segmentada. Pero se observó que no es correcta. Se copió a este fichero y se ha ido modificando con los colores reales que se muestran cuando se asignan los IDs. Pero todavía no es perfecta ya que no se han probado todos los IDs, solo unos pocos. Si se requiere el uso de nuevos IDs, habrá que obtener de la escena cuál es el color RGB asignado a este y modificar la tabla con el nuevo color.

### airsim_assets_manager.py
Este es el código que se encarga de introducir los obstáculos en la escena y darle las trayectorias obtenidas de `dynamics.json`. Fue código aportado por catec en el proyecto Colibrí y que se ha modificado para cumplir con nuestros objetivos.

### airsim_simulation_runner.py
Es el script de entrada que parsea las configuraciones, genera las trayectorias y lanza el [manager](#airsim-assets-manager). Código aportado por catec en el proyecto Colibrí y que se ha modificado para cumplir con nuestros objetivos.

### track_waypoints.py
Es el script de vuelo del UAV ownship en la simulación (PX4). Controla el dron principal siguiendo la secuencia de waypoints definida en el YAML. Es también el maestro de tiempo para sincronizar los objetos dinámicos en la escena.

[PENDIENTE] Cuando se pueda controlar el dron con Veronte correctamente, habrá que sincronizarlo con los objetos dinámicos de la escena tal y como hace este script.

### apply_simulation_config.py
Settings es el archivo que guarda la configuración de la escena AirSim. `setup.py` genera settings.json cada vez que se lanza la escena con la información que obtiene de los archivos de configuración de la carpeta settings (uav_veronte.json, config_simulation.json, sensors.json, etc.). Pero, para poder guardar todas estas configuraciones sin necesidad de duplicar ficheros, en la carpeta `sw_airsim/items/sim/` se guarda un JSON y un YAML por simulación con toda esta información.

El objetivo de este script es: cuando se tiene una configuración guardada en `sw_airsim/items/sim/{sim}.json, se llama a `./apply_simulation_config {sim}` y se aplica esta configuración a todos los ficheros de configuración de la carpeta settings.

### save_simulation_config.py
Settings es el archivo que guarda la configuración de la escena AirSim. `setup.py` genera settings.json cada vez que se lanza la escena con la información que obtiene de los archivos de configuración de la carpeta settings (uav_veronte.json, config_simulation.json, sensors.json, etc.). Pero, para poder guardar todas estas configuraciones sin necesidad de duplicar ficheros, en la carpeta `sw_airsim/items/sim/` se guarda un JSON y un YAML por simulación con toda esta información.

El objetivo de este script es: cuando se tiene una configuración que se ha utilizado en la carpeta settings y se quiere guardar, se llama a `./save_simulation_config.sh {sim}` y se guarda esta configuración en `sw_airsim/items/sim/{sim}.yaml` (las trayectorias del ownship) y en `sw_airsim/items/sim/{sim}.json` (el resto de la configuración).

### simulation_config.sh
Dos opciones:
- Si se llama como `simulation_config.sh apply {sim}` llama a: `apply_simulation_config.py {sim}`.
- Si se llama como `simulation_config.sh save {sim}` llama a: `save_simulation_config.py {sim}`.

### build_trajectories.py
Toma el fichero de encuentros (`all_encounters.h5` por defecto), que tiene encuentros aéreos entre el dron y un intruso, y convierte los datos a los JSON de configuración de la simulación: la trayectoria del intruso la guarda en {sim}.json (para `airsim_assets_manager.py`) y la del dron (ownship) la guarda en el YAML de waypoints (`{sim}.yaml` para `track_waypoints.py`). El parámetro `--scale-xy` escala las trayectorias en el plano horizontal, adaptándolas al tamaño del mundo (porque las trayectorias tienen longitudes de unos 14 km y las simulaciones para generar los datos serían demasiado largas).

### convert_images_to_video.sh
Postprocesado. Convierte las grabaciones de imágenes PNG que genera AirSim en vídeos MP4 usando ffmpeg. Busca en `records/` las carpetas de grabación con formato timestamp. Por cada carpeta que tenga el subdirectorio, genera un MP4 a 30 fps. Guarda los vídeos en `video_records/` (o el pasado como segundo argumento). Sirve para revisar visualmente las sesiones de captura sin tener que observarlas imagen a imagen y poder subir vídeos a las pull requests.

### build_and_launch_trajectories.sh
Llama a:
- build_trajectories.py: toma el fichero de encuentros (`all_encounters.h5` por defecto), que tiene encuentros aéreos entre el dron y un intruso, y convierte los datos a los JSON de configuración de la simulación: la trayectoria del intruso la guarda en {sim}.json (para `airsim_assets_manager.py`) y la del dron (ownship) la guarda en el YAML de waypoints (`{sim}.yaml` para `track_waypoints.py`). El parámetro `--scale-xy` escala las trayectorias en el plano horizontal, adaptándolas al tamaño del mundo (porque las trayectorias tienen longitudes de unos 14 km y las simulaciones para generar los datos serían demasiado largas).
- `simulation_config.sh apply {sim}`: aplica la configuración del JSON de simulación seleccionado a los ficheros activos en settings haciendo que AirSim arranque el mundo con esa configuración.
- `launch_px4.sh -w {world} --waypoints_control --bounding_box_simulation`: lanza todo el entorno docker con: control de waypoints activa (se llama a `track_waypoints.py`) para que el dron siga los waypoints del YAML generado, bounding box simulation activa (se llama a `segmentation_dataset_builder.py`) para capturar imágenes y generar datos sintéticos.

### debug_udp.py
Herramienta de diagnóstico para comprobar si el puente UDP con OPS está bien configurado y accesible. Prueba las interfaces de red disponibles, si el puerto local está abierto, si el puerto UDP está escuchando, si se puede hacer bind local, intenta abrir un socket UDP para detectar conflictos de puerto ocupado, verifica la conectividad de envío al remoto y muestra la configuración esperada del bridge.

### verify_sensors.py
Herramienta de validación para comprobar que los sensores de AirSim están bien configurados para Veronte. Carga la configuración real de sensores desde `settings/sensors.json` y agrupa por tipo. Verifica sensores por API de AirSim: lee datos, comprueba si responden y mide la frecuencia real. También verifica sensores por ROS topics: comprueba que existen los topics esperados, se suscribe y mide la frecuencia de publicación, y reporta los tipos de mensaje detectados. Presenta un resumen final.

Modos de uso: --api-only (solo verifica la API), --ros-only (solo verifica ROS topics), --duration {x} (cambia la duración de la medida) y --vehicle {x} (cambia el vehículo del que lee los sensores).

### LAUNCH
Inicialmente `launch.sh` era el launcher que iniciaba la simulación. Se utilizaba PX4. Como en este caso hemos introducido Veronte y PX4 es un autopiloto a eliminar (aunque todavía no se ha eliminado porque no se ha completado la integración de Veronte), se ha creado `launch_px4.sh` para ejecuciones con PX4 y `launch_veronte.sh` para ejecuciones con Veronte.

Para iniciar la simulación solo es necesario llamar al launch indicando el mundo a ejecutar. Por ejemplo `./launch_veronte.sh -w LondonWorld`. Con `./launch_veronte.sh --help` se puede observar todas las opciones de uso.

El control de autopiloto puede ser a través de PyVeronte si se llama con `./launch_veronte.sh -w LondonWorld --pyveronte`, o a través del desarrollo de APPs (en progreso).

## Problemas conocidos
Problemas conocidos:
- Crash del simulador justo al arrancar:
  - Puede ser porque el PawnBP definido no existe en el paquete. Comprobar no haberlo eliminado al actualizar el Plugin de AirSim.
  - Dron inestable: se ha activado la simulación de físicas en el Blueprint y choca con la definición en AirSim.
  - Puede ser un error en la escritura de `settings.json`.
  - Configuración demasiado compleja que el ordenador no soporta. Un mundo demasiado complejo.

- No se inician los Dockers:
  - Comprobar el permiso de acceso del terminal al Docker del equipo.
  - Comprobar que se esté utilizando el Docker default y no el de escritorio.
  - Comprobar variables de entorno: ROS_IP=127.0.0.1, ROS_MASTER_URI=http://127.0.0.1:11311.

## Referencias
- Documentación oficial AirSim: https://microsoft.github.io/AirSim/
- AirSim settings: https://microsoft.github.io/AirSim/settings/

