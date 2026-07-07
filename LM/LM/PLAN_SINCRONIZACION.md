# Plan de Sincronización CAN ↔ RTSP

## 1. Análisis de Fuentes de Tiempo

### 1.1 Timestamp CAN (Veronte)
- **Archivo**: `items/_sw_perception/items/sw_gnssdenied/items/sw_wvlibs/code/source/CAN_parser.cpp`
- **Función**: `deserialize_pose_packet(...)` (línea 26).
- **Extracción** (línea 36 y 46):
  ```cpp
  Uint32 t32 = ((Uint32*)buffer)[9];
  msg.timestamp = *((Real*)&t32);   // Real == float
  ```
- **Tipo**: `float` (4 bytes) en **segundos** desde el arranque del Veronte.
- **Resolución**: ~119 ns en t≈0, pero degradándose con el tiempo (ver §5).
- **Frecuencia de actualización**: la del bus CAN (paquetes Veronte de pose, normalmente 50–100 Hz).

### 1.2 Tick RTSP (smolrtsp)
- **Archivo**: `items/_sw_perception/items/sw_rtsp/code/source/smolrtsp_wrapper.c`
- **Constantes** (líneas 33–34):
  ```c
  #define VIDEO_SAMPLE_RATE  90000   // Hz, reloj RTP estándar para vídeo
  #define VIDEO_FPS          30
  ```
- **Estado** (línea 87): `uint32_t timestamp;` (campo de `VideoCtx`).
- **Inicialización** (línea 575): `.timestamp = 0` al crear el stream.
- **Incremento** (línea 644, dentro de `send_video_packet_cb`):
  ```c
  ctx->timestamp += VIDEO_SAMPLE_RATE / VIDEO_FPS;   // 3000 por frame a 30 fps
  ```
- **Envío** (línea 754): `SmolRTSP_RtpTimestamp_Raw(ctx->timestamp)`.
- **Tipo**: `uint32_t` → wrap-around natural a `2^32 / 90000 ≈ 47721.86 s` (≈ 13 h 15 m).

## 2. Punto de Sincronización (Anclaje t0)

El servicio RTSP actualmente arranca con `timestamp = 0` cuando un cliente entra en PLAY (línea 575). El anclaje debe capturarse en el **mismo instante** en que se envía el primer frame al transporte RTP, para que el `tick0` y `can_t0` representen el mismo evento físico.

### 2.1 Variables globales de anclaje
Añadir en `smolrtsp_wrapper.c` (estado de sincronización del wrapper):

```c
// --- Sync anchor (CAN ↔ RTSP) ---
typedef struct
{
    bool      valid;        // true cuando ya se ha anclado el primer frame
    uint32_t  rtsp_tick0;   // tick RTP del primer frame transmitido
    double    can_t0;       // timestamp CAN (s) capturado en el mismo instante
} Sync_anchor;

static Sync_anchor g_sync_anchor = { false, 0u, 0.0 };

// Callback que el wrapper consulta para conocer el último timestamp CAN.
// El wrapper NO debe acceder al CAN_parser directamente; se inyecta una función.
typedef double (*Can_time_provider_t)(void* user_data);
static Can_time_provider_t g_can_time_provider = NULL;
static void*               g_can_time_user     = NULL;

void smolrtsp_set_can_time_provider(Can_time_provider_t cb, void* user_data)
{
    g_can_time_provider = cb;
    g_can_time_user     = user_data;
}
```

### 2.2 Captura del anclaje
En `send_video_packet_cb`, **justo antes** del primer `send_nalu` (alrededor de línea 754, dentro del bloque que envía el primer NALU del primer frame válido):

```c
if (!g_sync_anchor.valid && g_can_time_provider != NULL)
{
    g_sync_anchor.rtsp_tick0 = ctx->timestamp;     // típicamente 0
    g_sync_anchor.can_t0     = g_can_time_provider(g_can_time_user);
    g_sync_anchor.valid      = true;
}
```

> **Importante**: anclar en el envío real del primer NALU (no en `init`) porque entre la creación del stream y el primer `PLAY` puede haber latencia variable de cliente.

## 3. Cálculo del Ratio (Regla de Tres)

```
1 segundo CAN  ↔  VIDEO_SAMPLE_RATE ticks RTP  =  90000 ticks
1 tick RTP     ↔  1 / 90000 s  ≈  1.1111e-5 s
```

Constante derivada:

```c
static const double RTSP_TICKS_PER_SECOND = 90000.0;
static const double SECONDS_PER_RTSP_TICK = 1.0 / 90000.0;
```

## 4. Función de Conversión

```c
/**
 * Convierte un tick RTSP (uint32_t, reloj 90 kHz) al instante CAN equivalente
 * en segundos. Maneja el wrap-around de uint32_t restando módulo 2^32.
 *
 * Pre: g_sync_anchor.valid == true
 */
double get_can_time_from_tick(uint32_t current_tick)
{
    if (!g_sync_anchor.valid)
    {
        return -1.0;  // o NaN; el caller debe validar
    }

    // Resta unsigned: el wrap-around es exacto en módulo 2^32.
    uint32_t delta_ticks = current_tick - g_sync_anchor.rtsp_tick0;

    // Conversión a segundos en double (no float) para preservar resolución.
    double delta_seconds = (double)delta_ticks * SECONDS_PER_RTSP_TICK;

    return g_sync_anchor.can_t0 + delta_seconds;
}
```

### 4.1 Manejo del overflow del tick
- La resta `current_tick - rtsp_tick0` se hace en `uint32_t`: el lenguaje C garantiza aritmética módulo 2^32 para tipos sin signo, por lo que **un único wrap se compensa automáticamente**.
- **Limitación**: el método sólo es correcto durante una ventana de `2^32 / 90000 ≈ 47721.86 s`. Si el stream supera esa duración hay que llevar un contador de wraps:

```c
static uint64_t g_tick_high = 0;     // bits altos
static uint32_t g_last_tick = 0;

static uint64_t extend_tick(uint32_t t)
{
    if (t < g_last_tick) g_tick_high += (1ULL << 32);  // detectó wrap
    g_last_tick = t;
    return g_tick_high | t;
}
```

Y la conversión usa `uint64_t` extendido. **Recomendado** para cualquier aplicación operativa de la LM (vuelos > 13 h son improbables, pero el coste es despreciable y elimina el riesgo).

## 5. Precisión float vs. double

`msg.timestamp` es `float` (32 bits, ~7 dígitos significativos). Implicaciones:

| Tiempo Veronte | Resolución float | ¿Suficiente para 30 fps (33 ms)? |
|----------------|------------------|----------------------------------|
| 0–8.4 s        | ≤ 1 µs           | ✅                               |
| 8.4–8388 s     | ≤ 1 ms           | ✅                               |
| > 8388 s (~2 h)| ≤ 8 ms           | ⚠️ marginal                      |
| > 67000 s (~18 h)| ≤ 64 ms        | ❌ peor que un frame             |

**Mitigación**:
1. Mantener `can_t0` en `double` y trabajar siempre con **deltas** desde el anclaje (`delta = float_can_now - float_can_t0`). El delta es pequeño y no pierde precisión.
2. Refrescar el anclaje (`re-anchor`) cada N segundos (p. ej. cada 60 s) usando un par CAN/RTSP coherente. Esto acota el error de cuantización del float CAN.

```c
void smolrtsp_reanchor(uint32_t tick_now, double can_now)
{
    g_sync_anchor.rtsp_tick0 = tick_now;
    g_sync_anchor.can_t0     = can_now;
    g_sync_anchor.valid      = true;
}
```

## 6. Estrategia de Búsqueda en el Array de Poses

Asumimos un buffer circular ordenado de `DAA_gps_status` (o equivalente) en `Pcapturing` con timestamps monótonos.

### 6.1 Estructura
```cpp
struct Pose_entry
{
    double                       t_can;   // promovido a double al insertar
    CAN_parser::DAA_gps_status   pose;
};

// Buffer circular protegido por mutex; tamaño dimensionado a >= max_latencia * f_can.
// Ej: 5 s * 100 Hz = 500 entradas.
std::deque<Pose_entry> pose_history;   // o ring buffer fijo
std::mutex             pose_mutex;
```

### 6.2 Búsqueda del más cercano (binary search)
```cpp
const Pose_entry* find_closest_pose(double t_target)
{
    std::lock_guard<std::mutex> lk(pose_mutex);
    if (pose_history.empty()) return nullptr;

    // lower_bound sobre t_can
    auto it = std::lower_bound(
        pose_history.begin(), pose_history.end(), t_target,
        [](const Pose_entry& e, double t){ return e.t_can < t; });

    if (it == pose_history.begin()) return &*it;
    if (it == pose_history.end())   return &pose_history.back();

    auto prev = std::prev(it);
    return (std::abs(prev->t_can - t_target) <= std::abs(it->t_can - t_target))
           ? &*prev : &*it;
}
```

### 6.3 Validación de calidad
Rechazar si `|closest.t_can - t_target| > tolerancia` (sugerencia: `tolerancia = 1.5 / f_can`, p.ej. 15 ms a 100 Hz). Devolver puntero nulo y registrar pérdida de sincronía.

## 7. Cambios en `example_rtsp.cpp`

**Archivo**: `items/_sw_perception/code/test/example_rtsp.cpp`

### 7.1 Includes
```cpp
#include <smolrtsp_wrapper.h>      // exponer el setter del provider
#include <atomic>
#include <mutex>
```

### 7.2 Almacén compartido de timestamp CAN
Añadir antes de `main` (o como miembro de un singleton ligero):

```cpp
static std::atomic<double> g_last_can_time{ -1.0 };

extern "C" double can_time_provider_cb(void* /*user*/)
{
    return g_last_can_time.load(std::memory_order_relaxed);
}
```

### 7.3 Hilo lector de poses CAN
`Pcapturing` ya consume CAN; lo más limpio es que **`Pcapturing` publique** cada timestamp CAN recibido en `g_last_can_time` y empuje la pose al buffer circular del §6. Si por aislamiento no se quiere tocar `Pcapturing`, lanzar un hilo extra:

```cpp
std::thread can_pose_thread([can0]() {
    CAN_parser::DAA_gps_status msg;
    while (true)
    {
        can0->read_pose(msg);                          // bloqueante
        g_last_can_time.store(static_cast<double>(msg.timestamp),
                              std::memory_order_relaxed);
        // push a pose_history (ver §6.1) si se desea búsqueda histórica
    }
});
can_pose_thread.detach();
```

### 7.4 Registro del provider antes de `streaming->Run()`

```cpp
// Después de crear streaming, ANTES de Run():
smolrtsp_set_can_time_provider(&can_time_provider_cb, nullptr);

streaming->Run();
```

### 7.5 (Opcional) Re-anchor periódico
Hilo de bajo coste cada 60 s:

```cpp
std::thread reanchor_thread([](){
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(60));
        uint32_t tick = smolrtsp_get_current_tick();   // helper a exponer
        double   t    = g_last_can_time.load();
        if (t > 0) smolrtsp_reanchor(tick, t);
    }
});
reanchor_thread.detach();
```

## 8. Resumen de Verificación

| Riesgo                                  | Mitigación                                                          |
|-----------------------------------------|---------------------------------------------------------------------|
| Wrap-around `uint32_t` (~13 h)          | Resta unsigned módulo 2^32 + extensión a `uint64_t` opcional (§4.1) |
| Pérdida de precisión `float` Veronte    | Trabajar con deltas, mantener `can_t0` en `double`, re-anchor (§5)  |
| Latencia entre `init` y primer `PLAY`   | Anclar en envío del primer NALU, no en construcción del ctx (§2.2)  |
| Buffer de poses lleno / pose ausente    | Tolerancia configurable + retorno nulo con métrica de pérdida (§6.3)|
| Carrera entre lector CAN y conversor    | `std::atomic<double>` para t_can; mutex para el buffer histórico    |

## 9. Tarea de Compilación

`build rtsp_example` (Docker `ae3d260508c0`). Tras los cambios:

1. Reconstruir `librtsp.a` (cambios en `smolrtsp_wrapper.c` + cabecera nueva).
2. Reconstruir `libsw_perception.a` si la cabecera `smolrtsp_wrapper.h` se incluye desde headers públicos.
3. Reconstruir `rtsp_example` y desplegar a la Jetson Nano.
