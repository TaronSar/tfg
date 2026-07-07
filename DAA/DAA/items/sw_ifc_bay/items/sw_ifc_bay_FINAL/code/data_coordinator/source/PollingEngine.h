#pragma once

#include <vector>
#include <functional>
#include <poll.h>
#include <atomic>

// Alias para los manejadores de eventos para mayor claridad.
using EventHandler = std::function<void()>;

class PollingEngine {
public:
    PollingEngine();
    ~PollingEngine() = default;

    PollingEngine(const PollingEngine&) = delete;
    PollingEngine& operator=(const PollingEngine&) = delete;

    /**
     * @brief Registra un descriptor de archivo para ser monitorizado.
     * @param fd El descriptor de archivo del canal (socket, puerto serie).
     * @param read_handler Función que se llamará cuando haya datos para leer.
     * @param write_handler Función que se llamará cuando se pueda escribir sin bloqueo.
     */
    void register_channel(int fd, EventHandler read_handler, EventHandler write_handler);

    /**
     * @brief Habilita o deshabilita la monitorización de eventos de escritura para un fd.
     * @param fd El descriptor de archivo a modificar.
     * @param enable true para monitorizar eventos de escritura, false para dejar de hacerlo.
     */
    void set_write_polling(int fd, bool enable);

    /**
     * @brief Inicia el bucle principal de sondeo de eventos. Esta función es bloqueante.
     */
    void run();

    /**
     * @brief Detiene el bucle de sondeo de forma segura.
     */
    void stop();

private:
    // Estructura interna para asociar un fd con sus manejadores.
    struct ChannelHandler {
        EventHandler handle_read;
        EventHandler handle_write;
    };

    std::vector<struct pollfd> m_poll_fds;
    std::vector<ChannelHandler> m_handlers;
    
    // Mapa para encontrar rápidamente el índice en m_poll_fds a partir de un fd.
    // Asumimos que los fds no serán excesivamente grandes.
    std::vector<int> m_fd_to_index_map;

    std::atomic<bool> m_running;
};