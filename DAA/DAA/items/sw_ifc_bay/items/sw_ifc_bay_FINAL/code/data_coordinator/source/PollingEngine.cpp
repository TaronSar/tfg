#include "PollingEngine.h"
#include <iostream>
#include <cerrno>
#include <unistd.h>

// Un tamaño máximo razonable para el mapa de descriptores de archivo.
// La mayoría de los sistemas tienen un límite por defecto de 1024 fds por proceso.
constexpr int MAX_FDS = 1024;

PollingEngine::PollingEngine() : m_running(false) {
    m_fd_to_index_map.resize(MAX_FDS, -1);
}

void PollingEngine::register_channel(int fd, EventHandler read_handler, EventHandler write_handler) {
    if (fd < 0 || fd >= MAX_FDS) {
        std::cerr << "Error: Descriptor de archivo " << fd << " fuera de rango." << std::endl;
        return;
    }

    // Añadir el descriptor al vector de poll
    struct pollfd pfd;
    pfd.fd = fd;
    pfd.events = POLLIN; // Por defecto, solo escuchamos para lectura
    pfd.revents = 0;
    m_poll_fds.push_back(pfd);

    // Guardar los manejadores
    m_handlers.push_back({std::move(read_handler), std::move(write_handler)});

    // Mapear el fd a su nuevo índice en el vector
    m_fd_to_index_map[fd] = m_poll_fds.size() - 1;
}

void PollingEngine::set_write_polling(int fd, bool enable) {
    if (fd < 0 || fd >= MAX_FDS || m_fd_to_index_map[fd] == -1) {
        return; // fd no válido o no registrado
    }

    int index = m_fd_to_index_map[fd];
    if (enable) {
        m_poll_fds[index].events |= POLLOUT;
    } else {
        m_poll_fds[index].events &= ~POLLOUT;
    }
}

void PollingEngine::stop() {
    m_running.store(false);
}

void PollingEngine::run() {

    int timeout_ms = 100;

    int num_events = ::poll(m_poll_fds.data(), m_poll_fds.size(), timeout_ms);

    if (num_events < 0) {
        if (errno == EINTR) {
            return; // Simplemente regresa, el bucle principal volverá a llamar.
        }
        perror("Error en poll()");
        m_running.store(false); // Detiene el gateway en caso de error grave.
        return;
    }

    if (num_events == 0) {
        return; // Timeout, no pasó nada. Regresa para que el bucle principal continúe.
    }

    // Iterar UNA SOLA VEZ sobre los descriptores para procesar los eventos.
    for (size_t i = 0; i < m_poll_fds.size(); ++i) {
        const auto& pfd = m_poll_fds[i];

        if (pfd.revents == 0) {
            continue; // No hay eventos para este descriptor.
        }

        // Manejo de errores
        if (pfd.revents & (POLLHUP | POLLERR | POLLNVAL)) {
            std::cerr << "Error o desconexión en el descriptor de archivo " << pfd.fd << std::endl;
            continue;
        }

        // Evento de LECTURA disponible
        if (pfd.revents & POLLIN) {
            if (m_handlers[i].handle_read) {
                m_handlers[i].handle_read();
            }
        }

        // Evento de ESCRITURA posible
        if (pfd.revents & POLLOUT) {
            if (m_handlers[i].handle_write) {
                m_handlers[i].handle_write();
            }
        }
    }
}