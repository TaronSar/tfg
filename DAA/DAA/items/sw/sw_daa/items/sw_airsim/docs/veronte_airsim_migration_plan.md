# Plan de migración: Desacoplamiento de PX4 y migración a Veronte en AirSim

**Feature branch:** `feature/2964_data_from_pyveronte_into_airsim`  
**Fecha:** Junio 2026  

---

## Contexto y motivación

AirSim actualmente soporta dos modos de firmware para el control del multirrotor simulado:

- **PX4 SITL / ArduCopter (MAVLink):** proceso externo que se conecta vía protocolo MAVLink, recibe datos de sensores del simulador y envía comandos a los motores. El autopiloto externo cierra el lazo de control.
- **SimpleFlight:** firmware interno de AirSim que usa cinemática de verdad absoluta (*ground truth*) en lugar de sensores reales. No hay lazo de control externo — el control es interno.

**Decisión clave:** Dado que necesitamos que Veronte reciba datos de sensores raw y controle los motores (lazo de control externo), el modo SimpleFlight no es adecuado como solución final. Sin embargo, **se usará SimpleFlight como modo base del simulador** en la primera fase, inyectando comandos de motor vía Python API (`moveByMotorPWMsAsync`) que sobreescriben el controlador interno. Esto permite validar el bridge sin recompilar AirSim.

### Estrategia de implementación

| Fase | Enfoque | Ventaja | Limitación |
|------|---------|---------|------------|
| **Fase 1 (actual)** | SimpleFlight + bridge Python API | Sin recompilar AirSim, iteración rápida | SimpleFlight interno sigue corriendo (se pisas con PWMs) |
| **Fase 2 (futuro opcional)** | Tipo de vehículo `"veronte"` nativo en C++ | Limpio, sin conflicto de controladores, óptimo | Requiere recompilación de plugins Unreal |

El objetivo de esta migración es **eliminar la dependencia a PX4** y sustituirla por **Veronte HIL/SIL**, el autopiloto propio de Embention. La arquitectura final debe:

1. Leer los datos crudos de los sensores simulados por AirSim (IMU, GPS, barométrico, magnetómetro, altímetro, cámaras).
2. Inyectarlos a Veronte HIL o Veronte SIL a través del protocolo de comunicación de Veronte.
3. Recibir las salidas de Veronte (señales de actuadores / comandos de motor).
4. Aplicar esas salidas sobre la aeronave simulada en AirSim vía `moveByMotorPWMsAsync()`.

---

## Arquitectura objetivo

```
┌─────────────────────────────────────────────────────────────────┐
│                       CONTENEDOR: Simulator                     │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                  AirSim (Unreal Engine)                  │  │
│   │                                                          │  │
│   │  Física simulada ──► Sensores raw (IMU, GPS, Baro, Mag)  │  │
│   │  Motor PWM inputs ◄── AirSim API (Python / C++)          │  │
│   └─────────────────────────┬────────────────────────────────┘  │
│                             │ AirSim Python API (puerto 41451)  │
└─────────────────────────────┼───────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────────┐
           │                  │                      │
           ▼                  ▼                      ▼
┌────────────────────┐ ┌─────────────────┐ ┌────────────────────────┐
│ CONT: airsim       │ │ CONT: veronte   │ │ CONT: colibri_onboard  │
│                    │ │     _bridge     │ │                        │
│ airsim_ros_wrapper │ │                 │ │ • target_detector      │
│                    │ │ 1. Lee sensores │ │ • state_machine        │
│ Publica topics ROS:│ │ 2. → Veronte    │ │ • waypoint tracking    │
│ • /camera/image    │ │ 3. ← Actuadores│ │                        │
│ • /pose            │ │ 4. → AirSim PWM│ │ Suscrito a topics ROS  │
│ • /imu             │ │                 │ │ de airsim_ros_wrapper  │
└────────────────────┘ └────────┬────────┘ └────────────────────────┘
                                │
                                │ Protocolo Veronte HIL/SIL (UDP / Serial)
                                ▼
               ┌────────────────────────────────────┐
               │   Veronte SIL (contenedor dedicado) │
               │   — o hardware Veronte (HIL) —     │
               └────────────────────────────────────┘
```

### Flujos de datos

| Flujo | Función | Depende de PX4 | Estado con Veronte |
|-------|---------|----------------|-------------------|
| **Control de vuelo** | Sensores → autopiloto → motores | Sí (MAVLink) | Sustituido por `veronte_bridge` |
| **Percepción ROS** | AirSim → airsim_ros_wrapper → topics ROS (imágenes, pose) | **No** | Funciona sin cambios |
| **Misión/DAA** | colibri_onboard consume topics ROS para algoritmos | **No** | Funciona sin cambios |
| **Comandos de vuelo** | UAL → MAVROS → PX4 (takeoff, waypoints, land) | Sí | Se elimina o se sustituye backend |

> **Nota sobre colibri_onboard:** Este contenedor tiene dos roles:
> 1. **Percepción y misión** (target_detector, state_machine, etc.) — consume topics ROS del `airsim_ros_wrapper`. **Sigue funcionando sin PX4.**
> 2. **Backend de control de vuelo** (`entrypoint_ual_px4.sh` → MAVROS → PX4) — **se elimina** en la migración a Veronte, ya que Veronte gestiona el vuelo directamente.
>
> Por tanto, `colibri_onboard` se mantiene para funciones de percepción/misión pero pierde el nodo `ual_px4`.

---

## Hitos del desarrollo

---

### Hito 1 — Análisis del protocolo de integración Veronte HIL/SIL

**Objetivo:** Entender qué interfaz expone Veronte para recibir datos de sensores y devolver comandos de actuadores.

**Tareas:**
- [ ] Documentar el protocolo Veronte HIL: mensajes, frecuencias, formatos de datos (IMU, GPS, baro, magnetómetro).
- [ ] Documentar el protocolo Veronte SIL: si difiere del HIL, identificar diferencias de interfaz.
- [ ] Identificar el canal de comunicación: UDP socket, serial, shared memory, ROS topic, etc.
- [ ] Documentar el formato de salida de actuadores que devuelve Veronte (PWM, thrust/torque, velocidades de motor).
- [x] Decidir modo preferido para desarrollo inicial: **SIL** (todo software, sin hardware) para facilitar las primeras iteraciones.

**Criterio de aceptación:** Documento de interfaz Veronte HIL/SIL que especifique todos los mensajes necesarios, frecuencias de refresco esperadas y canal de comunicación.

---

### Hito 2a — Adaptación del entorno para soportar PX4 y Veronte (desconexión de PX4)

**Objetivo:** Permitir que el simulador arranque correctamente con el vehículo `"Veronte"` (`VehicleType: SimpleFlight`) sin dependencia de PX4, manteniendo compatibilidad con PX4 si se desea.

**Tareas:**
- [x] Ajustar `settings/internal/setup.py` para que soporte el argumento `veronte` (además de `px4`), generando un `settings.json` con vehículo `"Veronte"` y `VehicleType: SimpleFlight`.
- [x] Ajustar `settings/internal/uav_veronte.json` con la clave `"Veronte"` y los campos base correctos.
- [x] Actualizar `scripts/apply_simulation_config.py` para detectar si el vehículo es `"PX4"` o `"Veronte"` y guardar en el fichero correspondiente.
- [x] Actualizar `scripts/save_simulation_config.py` para detectar el tipo de vehículo desde el nombre de la simulación (`PX4_*` vs `Veronte_*`).
- [x] Actualizar `launch.sh` para no lanzar el contenedor `px4_sitl` ni el proceso `ual_px4` cuando se usa modo Veronte.
  - Finalmente se ha generado  `launch_px4.sh` y `launch_veronte.sh`. En el futuro se eliminará `launch_px4.sh`.
- [x] Confirmar que `SimMode: Multirotor` + `VehicleType: SimpleFlight` funciona con nombre de vehículo `"Veronte"` en `settings.json`.
- [x] Verificar que los topics ROS se publican correctamente bajo `/airsim_node/Veronte/...`.

**Criterio de aceptación:** El entorno completo arranca con `./launch.sh` en modo Veronte sin PX4. El simulador no crashea, los topics ROS se publican bajo `/airsim_node/Veronte/`, y el sistema puede volver a modo PX4 cambiando el argumento.

---

### Hito 2b — Configuración y validación de sensores para Veronte SIL

**Objetivo:** Asegurar que todos los sensores necesarios para Veronte SIL están configurados en `settings.json` y accesibles vía AirSim API y topics ROS.

**Tareas:**
- [x] Identificar qué sensores adicionales necesita Veronte SIL que no estén ya configurados (según Hito 1).
- [x] Añadir al `settings.json` los sensores faltantes (ej: barómetro, magnetómetro si no estaban habilitados como SensorType).
- [x] Verificar que todos los sensores son accesibles vía AirSim Python API:
  - `getImuData(vehicle_name="Veronte")`
  - `getGpsData(vehicle_name="Veronte")`
  - `getBarometerData(vehicle_name="Veronte")`
  - `getMagnetometerData(vehicle_name="Veronte")`
  - `getDistanceSensorData(vehicle_name="Veronte")`
- [x] Escribir un script de verificación (`verify_sensors.py`) que conecte a AirSim y muestre los datos crudos de cada sensor con su frecuencia de muestreo real.
- [x] Verificar que los topics ROS correspondientes publican datos coherentes:
  - `/airsim_node/Veronte/imu/imu`
  - `/airsim_node/Veronte/gnss/gps`
  - `/airsim_node/Veronte/barometer/barometer`
  - `/airsim_node/Veronte/magnetometer/magnetometer`
  - `/airsim_node/Veronte/distance/distance_sensor_up`
  - `/airsim_node/Veronte/distance/distance_sensor_down`
- [x] Medir la frecuencia real de publicación de cada topic en el entorno Docker.
- [x] Documentar qué sensores están disponibles y a qué frecuencia para el bridge.

**Criterio de aceptación:** Script `verify_sensors.py` ejecuta sin errores y muestra datos coherentes de todos los sensores. Todos los topics ROS publican a las frecuencias esperadas. Los sensores necesarios para Veronte SIL están operativos.

---

### Hito 3 — Implementación del bridge AirSim ↔ Veronte

**Objetivo:** Crear el proceso de integración que conecta AirSim con Veronte, cerrando el lazo de control.

#### 3a — Lectura de sensores AirSim y escritura hacia Veronte SIL

**Objetivo:** Leer los datos crudos de sensores publicados por AirSim vía ROS topics, y escribirlos en Veronte SIL a través de PyVeronte (wrapper ctypes de `libVeronteSO__sil.so`). El bridge corre como nodo ROS a 200 Hz.

**Ubicación del código:** `items/sw/sw_daa/_sw_perception/items/sw_gnssdenied/items/sw_rosws/src/veronte_sil/scripts/`

**Tareas:**
- [x] Crear nodo ROS `airsim_veronte_bridge.py` con loop a 200 Hz (read → write → step → read outputs → write AirSim).
- [x] Definir interfaces abstractas: `ReadData` (ABC) y `WriteData` (ABC: start/stop/write/step).
- [x] Implementar `AirSimReader`: suscripción a topics ROS de IMU, GPS, barómetro, magnetómetro y odometría; expone `get_snapshot()` thread-safe con copia profunda (`SensorSnapshot.copy()`).
- [x] Implementar cálculo de sensores derivados (presión dinámica desde velocidad, GPS time desde clock del sistema).
- [x] Implementar `VeronteSILWriter`: serializa `SensorSnapshot` completo a PyVeronte SIL (writeImu con rotaciones de montaje, writeStp, writeQinf + TAS, writeMag con rotación de montaje, writeGnss, writeRnedRaw, writeGnssTime). Añade `reset_if_requested()`.
- [x] Centralizar configuración en `bridge/config.py`: nombres de sensores AirSim, capacidades HW (1 IMU, 1 MAG, 2 GNSS, 1 STP), templates de topics ROS, matrices de rotación de montaje.
- [x] Configurar variables de diagnóstico: `pushRvarRequest`, `pushBvarRequest`, `pushUvarRequest`.
- [x] Configurar `writeUvar([1010], [10])` para el filtro de navegación.
- [x] Verificar que no se necesita conversión de marcos de referencia (AirSim publica sensores individuales ya en body/NED).
- [x] Preparar escritura de lidar (implementada pero deshabilitada — no se usa actualmente).

**Criterio de aceptación:** El bridge arranca, se conecta a PyVeronte SIL, escribe todos los sensores configurados, estos se observan en OPS.

#### 3b — Recepción de outputs Veronte y control de motores en AirSim ✓ COMPLETADO

**Tareas:**
- [x] Implementar `VeronteSILReader`: lee RVARs 3110–3113 (RPM motores) y actitud via `get_step_output().ypr` tras cada step.
- [x] Implementar `VeronteOutputSnapshot`: dataclass con `motor_outputs[4]`, `roll`, `pitch`, `yaw`, `throttle`.
- [x] Implementar `AirSimWriter`: conecta a AirSim API (`MultirotorClient`), convierte RPM → PWM (`×0.0001538 + 0.1`, clampeado a 1.0) y envía via `moveByMotorPWMsAsync`.
- [x] Avanzar reloj de simulación con `simStep(dt)` tras cada comando de motor.
- [x] Integrar output path en el ciclo 200 Hz del bridge: ejecutado post-step.
- [x] Gestionar reset: re-adjuntar `VeronteSILReader` a la nueva instancia PyVeronte tras `reset_if_requested()`.

#### 3c — Gestión del ciclo de vida y errores (PARCIALMENTE COMPLETADO)

**Tareas:**
- [x] Implementar `reset_if_requested()` en `VeronteSILWriter`: reinicia SIL y re-adjunta reader automáticamente.
- [x] Añadir logs con `loguru` para diagnóstico del bridge (rotaciones, outputs, estado Veronte BVAR/UVAR).
- [x] Implementar lógica de reconexión si Veronte no está disponible al arranque.
- [ ] Exponer métricas: frecuencia efectiva de envío/recepción, número de mensajes perdidos.

**Criterio de aceptación:** La aeronave en AirSim es controlable desde Veronte SIL. Un vuelo básico (despegue, hover, aterrizaje) se completa sin que el simulador crashee.

---

### Hito 4 — [FUTURO OPCIONAL] Adaptación de la capa C++ de AirSim (tipo de vehículo nativo)

> **Nota:** Este hito NO es necesario para la integración funcional. La Fase 1 (SimpleFlight + bridge vía Python API) es suficiente para operar. Este hito solo es necesario si se detectan problemas de rendimiento/latencia por tener SimpleFlight corriendo en paralelo, o si se quiere una integración más limpia a nivel de arquitectura.

**Objetivo:** Registrar `"veronte"` como tipo de vehículo nativo en AirSim, eliminando la necesidad de SimpleFlight como intermediario.

**Tareas:**
- [ ] Añadir constante `kVehicleTypeVeronte = "veronte"` en `AirSimSettings.hpp`.
- [ ] Crear clase `VeronetMultiRotorParams.hpp` análoga a `Px4MultiRotorParams.hpp`, con la configuración física del airframe Colibri/DAA.
- [ ] Registrar el nuevo tipo en `MultiRotorParamsFactory.hpp`:
  ```cpp
  else if (vehicle_setting->vehicle_type == AirSimSettings::kVehicleTypeVeronte) {
      config.reset(new VeronteMultiRotorParams(vehicle_setting, sensor_factory));
  }
  ```
- [ ] Crear clase `VeronteApi.hpp` que implemente `MultirotorApiBase`:
  - En lugar de firmware interno (SimpleFlight) o MAVLink (PX4), delega el control a través del bridge externo.
  - Implementar `commandMotorPWMs()` aplicando directamente los valores recibidos del bridge.
  - Implementar `getKinematicsEstimated()` devolviendo estado desde la física del simulador.
- [ ] Actualizar `AirSimSettings.hpp` líneas 819 y 1268 para que `kVehicleTypeVeronte` sea tratado como tipo multirotor válido (no como MAVLink).
- [ ] Recompilar los plugins de AirSim (`build.sh`).
- [ ] Actualizar `settings.json` generado por `setup.py` para usar `"VehicleType": "veronte"`.

**Criterio de aceptación:** El simulador arranca con `VehicleType: veronte` sin recurrir a SimpleFlight ni PX4. El `MultiRotorParamsFactory` instancia correctamente el nuevo tipo.

---

### Hito 5 — Adaptación de la infraestructura Docker y scripts de lanzamiento

**Objetivo:** Eliminar el contenedor `px4_sitl` del flujo de simulación y añadir el nuevo contenedor del bridge Veronte.

**Tareas:**
- [ ] Crear `Dockerfiles/entrypoints/veronte_bridge/entrypoint_veronte_bridge.sh`.
- [ ] Crear imagen Docker `veronte_bridge` con las dependencias necesarias (airsim Python client, dependencias del protocolo Veronte).
- [ ] Actualizar `launch.sh`:
  - Eliminar la función/llamada `start_px4_sitl` (o condicionarla con flag `autopilot_type`).
  - Añadir `start_veronte_bridge()` que arranque el nuevo contenedor.
  - Actualizar la llamada a `setup.py` para pasar el argumento correcto.
- [ ] Eliminar `scripts/run_px4_sitl.sh` o marcar como deprecado.
- [ ] Actualizar `settings/internal/setup.py`:
  - Limpiar el argumento `simpleflight` y renombrarlo a `veronte` para mayor claridad.
  - Asegurarse de que `uav_veronte.json` produce solo la clave `"Veronte"` con el `VehicleType` correcto.
- [ ] Actualizar `README.md` del proyecto con el nuevo flujo de lanzamiento.

**Criterio de aceptación:** `./launch.sh` arranca el entorno completo con Veronte SIL sin requerir el contenedor `px4_sitl`. El comando `./settings/internal/setup.py veronte` genera un `settings.json` válido.

---

### Hito 6 — Validación HIL con hardware Veronte real

**Objetivo:** Probar la integración con hardware Veronte físico (HIL) en lugar del software SIL.

**Tareas:**
- [ ] Verificar que el bridge soporta el canal de comunicación físico (serial/USB) para HIL.
- [ ] Ajustar latencias y frecuencias de muestreo para operar con hardware real.
- [ ] Validar transformaciones de marcos de referencia con datos reales del hardware.
- [ ] Documentar el procedimiento de conexión HIL (cableado, configuración de puertos, parámetros).
- [ ] Realizar prueba de vuelo completa: despegue → navegación → aterrizaje.

**Criterio de aceptación:** La aeronave simulada en AirSim es controlada por hardware Veronte real a través de la interfaz HIL. El vuelo de validación se completa satisfactoriamente.

---

### Hito 7 — Integración con la cadena de misión DAA existente

**Objetivo:** Asegurar que el resto de la cadena (detección de obstáculos, predicción de conflictos, colibri ground) sigue funcionando con el nuevo autopiloto.

**Tareas:**
- [ ] Verificar que `airsim_simulation_runner.py` (colibri interface) sigue obteniendo la pose del vehículo correctamente con el nuevo nombre `"Veronte"`.
- [ ] Actualizar referencias al nombre de vehículo en todos los scripts Python del directorio `Dockerfiles/entrypoints/airsim/`.
- [ ] Verificar la compatibilidad de las cámaras y sensores DAA (lidar_right, lidar_left, camera_forward) con el nuevo tipo de vehículo.
- [ ] Ejecutar la suite de pruebas de integración completa (trayectorias, evitación de colisiones).
- [ ] Actualizar `simulation_config.sh` y `config_simulation.json` para reflejar el nuevo autopiloto.

**Criterio de aceptación:** Una simulación end-to-end completa (lanzamiento → misión DAA → aterrizaje) funciona con Veronte como autopiloto sin regresiones.

---

### Hito 8 — Envío y ejecución de trayectorias completas en AirSim vía Veronte

**Objetivo:** Validar que se puede cargar una misión (secuencia de waypoints / trayectoria) en Veronte y que la aeronave en AirSim la ejecuta de principio a fin de forma autónoma, cerrando el lazo de navegación completo.

**Tareas:**
- [ ] Definir el formato de trayectoria compatible con Veronte (lista de waypoints con posición, velocidad, heading, altitud, y acción en cada punto).
- [ ] Implementar el envío de una misión/trayectoria a Veronte SIL a través de la interfaz definida en Hito 1 (Veronte SDK / protocolo propietario).
- [ ] Verificar que Veronte SIL acepta la misión, pasa a modo navegación autónoma y genera comandos de actuación durante toda la trayectoria.
- [ ] Confirmar que el bridge traduce correctamente los comandos de Veronte a lo largo de toda la misión (no solo en hover):
  - Transiciones entre waypoints (curvas, cambios de altitud, cambios de velocidad).
  - Gestión de final de misión (loiter / RTL / aterrizaje).
- [ ] Crear un script de validación (`test_trajectory.py`) que:
  1. Cargue una trayectoria predefinida en Veronte.
  2. Inicie la misión.
  3. Registre la posición real de la aeronave en AirSim durante la ejecución.
  4. Compare la trayectoria ejecutada vs la planificada (error lateral y longitudinal).
- [ ] Validar con al menos 3 trayectorias tipo:
  - Rectangular (waypoints rectos con giros de 90°).
  - Circular / curvilínea.
  - Con cambios de altitud (ascenso + descenso + hover intermedio).
- [ ] Medir métricas de seguimiento: error máximo de posición, desviación media, tiempo total vs esperado.
- [ ] Verificar que Veronte reporta correctamente el progreso de la misión (waypoint alcanzado, misión completada).

**Criterio de aceptación:** Al menos 3 trayectorias predefinidas se ejecutan de forma completa y autónoma en AirSim controladas por Veronte SIL/HIL. El error de seguimiento está dentro de márgenes aceptables (a definir) y Veronte señaliza correctamente la finalización de la misión.

---

## Resumen de dependencias entre hitos

```
Fase 1 (implementación actual):

Hito 1 (Protocolo Veronte)
    └─► Hito 2a (Adaptación entorno: PX4 / Veronte seleccionable)
            └─► Hito 2b (Configuración y validación de sensores)
                    └─► Hito 3 (Bridge Python API: sensores + moveByMotorPWMsAsync)
                            └─► Hito 5 (Docker + scripts)
                                    ├─► Hito 6 (HIL)
                                    ├─► Hito 7 (DAA integration)
                                    └─► Hito 8 (Trayectorias completas vía Veronte)

Fase 2 (futuro opcional):

Hito 4 (C++ nativo — solo si se necesita optimización)
```

---

## Decisiones de diseño

| Decisión | Opciones | Decisión tomada |
|---|---|---|
| Modo de integración con AirSim | SimpleFlight + API override vs tipo C++ nativo | **SimpleFlight + override vía `moveByMotorPWMsAsync`** (Fase 1) |
| Modo de integración inicial | HIL (hardware) vs SIL (software) | **SIL** para desarrollo inicial |
| Arquitectura del bridge | Proceso Python externo vs plugin C++ AirSim | **Proceso Python externo** (menor riesgo, más fácil de iterar) |
| Canal de comunicación Veronte | UDP, Serial, ROS | A definir en Hito 1 |
| Marco de referencia | NED, ENU, body frame | Verificar en Hito 2, documentar conversiones |
| Frecuencia del lazo cerrado | Fija vs adaptativa al ClockSpeed | Investigar impacto de `ClockSpeed: 0.5` |
| Tipo C++ nativo en AirSim | Sí vs No | **No** (Fase 1). Futuro opcional si hay problemas de rendimiento |

---

## Archivos clave del repositorio

| Archivo | Descripción | Estado |
|---|---|---|
| `settings/internal/setup.py` | Generador de `settings.json` | Modificado (soporte `simpleflight`/`veronte`) |
| `settings/internal/uav_veronte.json` | Configuración de vehículo Veronte | Existe (base) |
| `settings/internal/shared/settings.json` | Configuración runtime de AirSim | Generado con vehículo `"Veronte"` |
| `launch.sh` | Orquestador de contenedores tmux | Modificado (logs Docker) |
| `scripts/apply_simulation_config.py` | Aplica config de simulación | Modificado (soporte Veronte) |
| `scripts/save_simulation_config.py` | Guarda config de simulación | Modificado (soporte Veronte) |
| `airsim/AirLib/include/common/AirSimSettings.hpp` | Definición de tipos de vehículo | Sin cambios (Fase 1). Futuro opcional (Fase 2) |
| `airsim/AirLib/include/vehicles/multirotor/MultiRotorParamsFactory.hpp` | Factory de vehículos | Sin cambios (Fase 1). Futuro opcional (Fase 2) |
| `Dockerfiles/entrypoints/px4_sitl/` | Entrypoint PX4 SITL | **A eliminar** (Hito 5) |
| `scripts/run_px4_sitl.sh` | Script lanzamiento PX4 | **A deprecar** (Hito 5) |
