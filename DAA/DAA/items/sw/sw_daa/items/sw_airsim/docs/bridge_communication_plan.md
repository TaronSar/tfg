# Plan de comunicación: Bridge AirSim ↔ Veronte

**Feature branch:** `feature/2964_data_from_pyveronte_into_airsim`  
**Fecha:** Junio 2026  
**Estado:** Hito 3a completado (escritura de sensores). Hito 3b completado (lectura outputs Veronte y escritura en AirSim).

---

## 1. Visión general

El nodo **bridge** actúa como intermediario entre AirSim (simulador) y Veronte (autopiloto). Su responsabilidad es:

- **Entrada al bridge (desde AirSim):** Datos raw de sensores vía topics ROS publicados por `airsim_ros_wrapper`.
- **Salida del bridge (hacia Veronte):** Escritura de sensores mediante PyVeronte (ctypes sobre `libVeronteSO__sil.so`).
- **Entrada al bridge (desde Veronte):** Lectura de outputs de control (motores, actitud) vía `readRvar` + `get_step_output()` — implementado en `VeronteSILReader`.
- **Salida del bridge (hacia AirSim):** Comandos de motor vía `moveByMotorPWMsAsync()` — implementado en `AirSimWriter`.

El diseño se basa en **interfaces abstractas** (`ReadInputData` / `WriteInputData`) que permiten cambiar entre Veronte SIL y Veronte HIL sin modificar la lógica del bridge.

---

## 2. Arquitectura de comunicación (implementada)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        NODO ROS: airsim_veronte_bridge                           │
│                              (loop 200 Hz)                                       │
│                                                                                  │
│  ┌────────────────────┐  get_snapshot()   ┌──────────────────────┐               │
│  │  AirSimReader      │ ────────────────► │ VeronteSILWriter     │               │
│  │  (ReadData)        │   SensorSnapshot  │ (WriteData)          │               │
│  │                    │                   │                      │               │
│  │  - Suscribe topics │                   │ - write(snapshot)    │               │
│  │  - Computa derivados                   │ - step(dt)           │               │
│  │  - Thread-safe lock│                   │ - reset_if_requested │               │
│  └────────────────────┘                   └──────────────────────┘               │
│           ▲                                          │                           │
│           │                                          │ ctypes (in-process)       │
│           │                                          ▼                           │
│           │                               ┌──────────────────────┐               │
│           │                               │   libVeronteSO__sil  │               │
│           │                               │   (PyVeronte)        │               │
│           │                               └──────────────────────┘               │
│           │                                          │                           │
│           │                               ┌──────────┴───────────┐               │
│           │                               ▼                      ▼               │
│           │                   ┌───────────────────┐  ┌────────────────────────┐  │
│           │                   │ VeronteSILReader  │  │  OPS_Usb_UdpBridge     │  │
│           │                   │ (ReadData)        │  │  UDP ↔ USB con OPS     │  │
│           │                   │                   │  └────────────────────────┘  │
│           │                   │ - read()          │                              │
│           │                   │   motores (RVARs) │                              │
│           │                   │   actitud (ypr)   │                              │
│           │                   └───────────────────┘                              │
│           │                               │  VeronteOutputSnapshot               │
│           │                               ▼                                      │
│           │                   ┌───────────────────┐                              │
│           │                   │  AirSimWriter     │                              │
│           │                   │  (WriteData)      │                              │
│           │                   │                   │                              │
│           │                   │ - RPM → PWM       │                              │
│           │                   │ - moveByMotorPWMs │                              │
│           │                   └───────────────────┘                              │
│           │                               │                                      │
└───────────┼───────────────────────────────┼──────────────────────────────────────┘
            │ ROS Topics                    │ AirSim API
            │ /airsim_node/Veronte/...       │ moveByMotorPWMsAsync / simStep
┌───────────────────────┐          ┌────────┴─────────────────┐
│  airsim_ros_wrapper   │◄─────────│    AirSim / Unreal        │
│  (Unreal Engine +     │          │  (simulador de vuelo)     │
│   AirSim plugin)      │          └───────────────────────────┘
└───────────────────────┘
```

> **Nota:** La comunicación con Veronte SIL es **in-process** via ctypes (no UDP). Para HIL futuro se implementará un backend con comunicación serial/UDP.

---

## 3. Definición de interfaces (Entradas / Salidas)

### 3.1 Entradas al bridge (sensores de AirSim → bridge)

Los sensores se leen via **suscripción a topics ROS** (publicados por `airsim_ros_wrapper`), no por API directa.

| Sensor | Topic ROS | Cantidad | Msg type | Frecuencia |
|--------|-----------|----------|----------|------------|
| IMU | `/airsim_node/Veronte/{name}/imu` | 3 | `sensor_msgs/Imu` | 200 Hz |
| GPS | `/airsim_node/Veronte/{name}/gps` | 2 | `sensor_msgs/NavSatFix` + `geometry_msgs/TwistStamped` | 5–10 Hz |
| Barómetro | `/airsim_node/Veronte/{name}/barometer` | 3 | `airsim_ros_pkgs/Altimeter` | 50 Hz |
| Magnetómetro | `/airsim_node/Veronte/{name}/magnetometer` | 4 | `sensor_msgs/MagneticField` | 50 Hz |
| Odometría | `/airsim_node/Veronte/odom_local_ned` | 1 | `nav_msgs/Odometry` | 200 Hz |

**Estructura interna (dataclasses en `bridge/ReadInputData.py`):**

```python
@dataclass
class ImuData:
    acc: List[float]    # [ax, ay, az] m/s² (body)
    gyr: List[float]    # [gx, gy, gz] rad/s (body)
    temp: float         # K

@dataclass
class GnssData:
    fix: int            # 0/1
    fix_type: int       # 3=3D
    lon: int            # deg × 1e7 (wire format)
    lat: int            # deg × 1e7
    alt: int            # mm
    hacc: int           # mm
    vacc: int           # mm
    vn: int             # mm/s
    ve: int             # mm/s
    vd: int             # mm/s
    vel_acc: int        # mm/s

@dataclass
class BarometerData:
    pressure: float     # Pa
    temp: float         # K

@dataclass
class MagnetometerData:
    field: List[float]  # [mx, my, mz] Gauss (body)
    temp: float         # K

@dataclass
class SensorSnapshot:
    imu: List[ImuData]
    gnss: List[GnssData]
    barometer: List[BarometerData]
    magnetometer: List[MagnetometerData]
    dynamic_pressure: DynamicPressureData
    rned: List[RnedData]
    gps_time: GpsTimeData
    lidar: List[LidarData]
```

### 3.2 Outputs de Veronte → bridge → AirSim

#### Lectura de Veronte (`VeronteSILReader`)

| Señal | Fuente PyVeronte | Datos | Unidades |
|-------|-----------------|-------|----------|
| Motores (4 canales) | `readRvar([3110, 3111, 3112, 3113])` | motor_outputs[4] | RPM (float) |
| Actitud | `get_step_output().ypr` | roll, pitch, yaw | rad |
| Throttle | Media de motores escalada | throttle | 0.0–1.0 |

**Conversión RPM → PWM (`AirSimWriter`):**
```
pwm[i] = clamp(rpm[i] × 0.0001538 + 0.1, 0.0, 1.0)   si rpm[i] > 50
pwm[i] = 0.0                                           si rpm[i] ≤ 50
```

#### Escritura a AirSim (`AirSimWriter`)

| Señal | API AirSim | Datos | Unidades | Frecuencia |
|-------|-----------|-------|----------|------------|
| Motor PWM (4 motores) | `moveByMotorPWMsAsync()` | pwm[0..3] | 0.0 – 1.0 (normalizado) | 200 Hz |
| Avance reloj simulación | `simStep(dt)` | dt | s | 200 Hz |

**Estructura interna (`VeronteOutputSnapshot`):**

```python
@dataclass
class VeronteOutputSnapshot:
    motor_outputs: List[float]   # [0..3] RPM de RVARs 3110-3113
    roll: float                  # rad (de step_output.ypr)
    pitch: float                 # rad
    yaw: float                   # rad
    throttle: float              # 0.0-1.0 (media de los 4 motores escalada)
```

### 3.3 Interfaz hacia Veronte (Abstracción implementada)

La interfaz de escritura se define en `bridge/WriteInputData.py`:

```python
class WriteInputData(ABC):
    """Interfaz abstracta para escribir datos de sensores al autopiloto."""

    @abstractmethod
    def start(self) -> None:
        """Inicializa la conexión con el autopiloto."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Cierra la conexión."""
        ...

    @abstractmethod
    def write(self, snapshot: SensorSnapshot) -> None:
        """Escribe un snapshot completo de sensores al autopiloto."""
        ...

    @abstractmethod
    def step(self, dt: float) -> float:
        """Avanza un paso de simulación. Retorna next_time."""
        ...
```

**Implementación actual:** `VeronteSILOwnshipWriter` (ctypes in-process).  
**Implementación futura:** `VeronteHILWriter` (serial/UDP hacia hardware real).

### 3.4 Backends de comunicación

#### Backend SIL (Software-in-the-Loop) — IMPLEMENTADO

```
Bridge ◄──── ctypes (in-process) ────► libVeronteSO__sil.so
```

| Parámetro | Valor |
|-----------|-------|
| Protocolo | ctypes (carga de .so en el mismo proceso) |
| Wrapper | PyVeronte (clase Python sobre ctypes) |
| DLL path | `VERONTE_DLL_PATH` env var o default en código |
| SD Image | `SD_IMAGE_PATH` env var o default en código |
| HW version | "4.8" (3 IMU, 4 MAG, 2 GNSS, 3 STP) |
| Time control | `writeRvar([3140], [dt])` + `step(sim_time)` |

#### Backend HIL (Hardware-in-the-Loop) — PENDIENTE

```
Bridge ◄──── Serial/USB ────► Veronte (hardware físico)
```

| Parámetro | Valor por defecto |
|-----------|-------------------|
| Protocolo | Serial (UART/USB) |
| Puerto | /dev/ttyUSBx |
| Baudrate | TBD (115200 / 921600) |
| Formato de mensajes | Protocolo Veronte HIL nativo |

---

## 4. Flujo de datos (secuencia temporal)

```
  airsim_ros_wrapper        Bridge (200 Hz loop)              Veronte SIL
       │                          │                              │
       │  ROS topics (sensores)   │                              │
       │ ────────────────────────►│                              │
       │                          │  write(snapshot)             │
       │                          │  ┌─ writeImu ×3             │
       │                          │  ├─ writeStp ×3             │
       │                          │  ├─ writeQinf              │
       │                          │  ├─ writeMag ×4            │
       │                          │  ├─ writeGnssRaw ×2        │
       │                          │  ├─ writeRnedRaw           │
       │                          │  └─ writeGnssTimeRaw       │
       │                          │ ─────────────────────────────►│
       │                          │                              │
       │                          │  step(dt)                    │
       │                          │  writeRvar([3140],[dt])      │
       │                          │ ─────────────────────────────►│ (procesa GNC/EKF)
       │                          │                              │
       │                          │  readRvar/readBvar (debug)   │
       │                          │ ◄─────────────────────────────│
       │                          │                              │
       │                          │  verontesil_reader.read()    │
       │                          │  readRvar([3110-3113])        │
       │                          │ ◄─────────────────────────────│ (motor RPM)
       │                          │  get_step_output().ypr        │
       │                          │ ◄─────────────────────────────│ (actitud)
       │                          │                              │
       │  airsim_writer.write()   │                              │
       │  moveByMotorPWMsAsync()  │  RPM → PWM (×0.0001538+0.1)  │
       │ ◄────────────────────────│                              │
       │  simStep(dt)             │                              │
       │ ◄────────────────────────│                              │
       │                          │                              │
       ...                       ...                            ...
```

**Latencia total objetivo del lazo cerrado:** < 10 ms (SIL es in-process, sin latencia de red).

---

## 5. Transformaciones de marcos de referencia

| Sistema | Convenio | Ejes | Estado |
|---------|----------|------|--------|
| AirSim (world) | NED | X=Norte, Y=Este, Z=Down | ✓ Verificado |
| Veronte (world) | NED | X=Norte, Y=Este, Z=Down | ✓ Verificado |
| Body frame AirSim | FRD | X=Forward, Y=Right, Z=Down | ✓ Verificado |
| Body frame Veronte | FRD | X=Forward, Y=Right, Z=Down | ✓ Verificado |

> **RESULTADO:** No se requiere conversión de marcos de referencia. AirSim publica los topics de sensores individuales (IMU, magnetómetro) ya en body frame FRD, y las posiciones/velocidades en NED. Esto difiere del código antiguo (`veronte_sil.py`) que leía de `/uav_0/ual/pose` en ENU y necesitaba conversión.

---

## 6. Estado de tareas

### Hito 3a — Escritura de sensores hacia Veronte SIL ✓ COMPLETADO

| ID | Tarea | Estado |
|----|-------|--------|
| T1 | Definir interfaces abstractas (ReadInputData, WriteInputData) | ✓ |
| T2 | Implementar `AirSimReader` (suscripción a topics ROS, snapshot thread-safe) | ✓ |
| T3 | Implementar `AirSimSensorsSimulation` (presión dinámica, GPS time) | ✓ |
| T4 | Implementar `VeronteSILOwnshipWriter` (serialización a PyVeronte) | ✓ |
| T5 | Implementar nodo principal `airsim_veronte_bridge.py` (loop 200 Hz) | ✓ |
| T6 | Configurar variables de diagnóstico (RVar, BVar, UVar) | ✓ |
| T7 | Verificar marcos de referencia (no se necesita conversión) | ✓ |

### Hito 3b — Lectura de outputs Veronte y escritura en AirSim ✓ COMPLETADO

| ID | Tarea | Estado |
|----|-------|--------|
| T8 | Implementar `VeronteSILReader` (lectura de RVARs motores + actitud) | ✓ |
| T9 | Leer motor outputs via RVARs 3110–3113 (RPM) y actitud via `get_step_output().ypr` | ✓ |
| T10 | Implementar `AirSimWriter`: RPM → PWM + `moveByMotorPWMsAsync()` + `simStep()` | ✓ |
| T11 | Integrar output path en `AirSim_Veronte_bridge` (ciclo post-step) | ✓ |
| T11b | Test end-to-end: despegue, hover, aterrizaje controlado por Veronte | Pendiente validación |

### Hito 3c — Gestión del ciclo de vida (PARCIALMENTE COMPLETADO)

| ID | Tarea | Estado |
|----|-------|--------|
| T12 | Gestión de reset de Veronte SIL (`reset_if_requested()`) | ✓ |
| T12b | Re-adjuntar `VeronteSILReader` a nueva instancia PyVeronte tras reset | ✓ |
| T13 | Métricas de latencia y pérdida de mensajes | Pendiente |

---

## 7. Variables de comunicación con Veronte

### Variables de escritura (bridge → Veronte)

| Método PyVeronte | Parámetros | Frecuencia | Descripción |
|------------------|------------|------------|-------------|
| `writeImu(id, acc, gyr, temp)` | id=0..2 | 200 Hz | 3 IMUs (HW 4.8) |
| `writeStp(id, press, temp)` | id=0..2, Pa, K | 200 Hz | 3 barómetros |
| `writeQinf(id, press, temp)` | id=0, Pa, K | 200 Hz | Presión dinámica (calculada) |
| `writeMag(id, mag, temp)` | id=0..3, Gauss, K | 200 Hz | 4 magnetómetros |
| `writeGnssRaw(id, ...)` | Wire: deg×1e7, mm, mm/s | 200 Hz | 2 GPS |
| `writeRnedRaw(id, ...)` | Wire: cm + deci-mm | 200 Hz | Posición relativa NED |
| `writeGnssTimeRaw(week, tow_ms)` | Semana GPS, TOW ms | 200 Hz | Tiempo GPS |
| `writeRvar([3140], [dt])` | dt en segundos | 200 Hz | Control de tiempo simulación |
| `writeUvar([1010], [4])` | Nº magnetómetros | 1× (init) | Config filtro navegación |

### Variables de lectura (Veronte → bridge)

| Tipo | IDs solicitados | Propósito |
|------|-----------------|-----------|
| RVar | 300, 500, 501, 502, 503, 505, 506, 507, 0, 100, 6, 7, 8 | Time, posición, velocidad, IAS, orientación |
| BVar | 50, 51, 52, 83, 85, 87, 88, 100, 130 | Health sensores, position fix, EKF state |
| UVar | 0, 1, 100, 150, 401 | Flight mode, phase, GNSS sats, nav source |

---

## 8. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación | Estado |
|--------|---------|------------|--------|
| Protocolo Veronte no documentado | Alto | Coordinar con equipo Veronte | ✓ Resuelto (PyVeronte disponible) |
| Diferencias en marcos de referencia | Medio | Validar con vuelo simple | ✓ Resuelto (ambos NED/FRD) |
| Frecuencia de sensores insuficiente | Medio | Medir frecuencias reales | ✓ Resuelto (200 Hz alcanzable) |
| Latencia del lazo cerrado > 10ms | Medio | `SteppableClock` + time control | Pendiente validación en 3b |
| Hardware HIL no disponible | Bajo | Priorizar SIL | SIL funcional, HIL futuro |

---

## 9. Criterios de aceptación globales

1. ✓ Los datos de sensores llegan a Veronte SIL con la frecuencia (200 Hz) y formato correctos.
2. ✓ El EKF de Veronte converge (RVar posición/orientación con valores coherentes).
3. ✓ No se requiere dependencia alguna de PX4 para el bridge.
4. ✓ Los outputs de Veronte (RVARs motores, actitud) se leen y aplican a AirSim cada ciclo (200 Hz).
5. El cambio entre backend SIL y HIL se realiza cambiando la implementación de `WriteData` / `ReadData` (pendiente HIL).
6. ✓ Los comandos de actuadores de Veronte se aplican a la aeronave simulada en < 10ms (SIL in-process).
7. Validación end-to-end: despegue, hover y aterrizaje controlado por Veronte — pendiente.
