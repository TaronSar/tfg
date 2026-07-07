#include "ProtocolGateway.h"
#include <iostream>
#include <arpa/inet.h>
#include <cstring> // Para memcpy

ProtocolGateway::ProtocolGateway(AppConfig config)
    : m_config(std::move(config)), m_shutdown_flag(false) {}

ProtocolGateway::~ProtocolGateway() {
    stop();
}

void ProtocolGateway::run() {
    m_outbound_can_queue = std::make_unique<MessageQueue<CanMessage>>(m_config.queue_size);
    m_outbound_serial_queue = std::make_unique<MessageQueue<SerialBuffer>>(m_config.queue_size);

    if (!setup_channels()) {
        std::cerr << "Error fatal: No se pudieron inicializar los canales de comunicación." << std::endl;
        return;
    }

    // El hilo principal ahora ejecuta un bucle que gestiona la escritura y el motor de sondeo.
    main_loop_logic();
}

void ProtocolGateway::stop() {
    m_shutdown_flag.store(true);
    m_polling_engine.stop();
}

bool ProtocolGateway::setup_channels() {
    if (!m_can_channel.open(m_config.can_interface_name)) return false;
    if (!m_serial_rx_channel.open(m_config.serial_rx.device, m_config.serial_rx.baud_rate)) return false;
    if (!m_serial_tx_channel.open(m_config.serial_tx.device, m_config.serial_tx.baud_rate)) return false;

    for (uint16_t port : m_config.udp_ports) {
        auto udp_channel = std::make_unique<UdpChannel>();
        if (!udp_channel->open(port)) return false;
        m_udp_channels[port] = std::move(udp_channel);
    }

    // Registrar canales de LECTURA en el motor de sondeo
    m_polling_engine.register_channel(
        m_can_channel.get_file_descriptor(),
        [this]() { this->handle_can_read(); },
        [this]() { this->handle_can_write(); }
    );
    m_polling_engine.register_channel(
        m_serial_rx_channel.get_native_handle(),
        [this]() { this->handle_serial_read(); },
        nullptr // El canal de escritura serie no se sondea para escritura
    );
    m_polling_engine.register_channel(
        m_serial_tx_channel.get_native_handle(),
        nullptr,
        [this]() { this->handle_serial_write(); }
    ); // El canal de escritura serie no se sondea para escritura

    // MODIFICACIÓN: Registrar TODOS los canales UDP en el motor de sondeo
    for (const auto& pair : m_udp_channels) {
        uint16_t port = pair.first;
        int fd = pair.second->get_file_descriptor();
        m_polling_engine.register_channel(
            fd,
            [this, port]() { this->handle_udp_read(port); },
            nullptr // No necesitamos un manejador de escritura para UDP en el poller
        );
    }

    return true;
}

void ProtocolGateway::main_loop_logic() {
    std::cout << "Gateway iniciado. Bucle principal en ejecución." << std::endl;
    while (!m_shutdown_flag.load()) {
        // Habilitar sondeo de escritura solo si hay algo en las colas
        m_polling_engine.set_write_polling(m_can_channel.get_file_descriptor(),!m_outbound_can_queue->is_empty());
        m_polling_engine.set_write_polling(m_serial_tx_channel.get_native_handle(),!m_outbound_serial_queue->is_empty());

        m_polling_engine.run(); // Esta llamada ahora tendrá un timeout para poder re-evaluar las colas
    }
    std::cout << "Gateway detenido." << std::endl;
}

void ProtocolGateway::handle_udp_read(uint16_t port) {
    UdpBuffer buffer;
    struct sockaddr_in src_addr;
    ssize_t sz = m_udp_channels[port]->receive_from(buffer, src_addr);

    if (sz <= 0) {
        std::cout << "DEBUG: Recibidos 0" << std::endl;
        return;
    }

    // Ruta: UDP -> CAN
    auto it_can = m_config.udp_to_can_rules.find(port);
    if (it_can!= m_config.udp_to_can_rules.end()) {
        CanMessage frame{}; // Inicialización a cero
        frame.can_id = it_can->second;
        frame.can_dlc = std::min(buffer.size(), static_cast<size_t>(CAN_MAX_DLEN));
        std::memcpy(frame.data, buffer.data(), frame.can_dlc);
        
        if (!m_outbound_can_queue->try_push(frame)) {
            std::cerr << "ERROR: Cola de salida CAN llena. Descartando mensaje UDP del puerto " << port << std::endl;
        }
        return;
    }

    // Ruta: UDP -> RS-485
    if (port == m_config.udp_to_rs485_port) {
        if (!m_outbound_serial_queue->try_push(buffer)) {
            std::cerr << "ERROR: Cola de salida Serial llena. Descartando mensaje UDP del puerto " << port << std::endl;
        }
    } else {
        std::cerr << "ERROR: No se encontró ninguna regla de enrutamiento para el puerto UDP " << port << std::endl;
    }
}

void ProtocolGateway::handle_can_read() {
    CanMessage frame;
    if (m_can_channel.read(frame)) {
        auto it = m_config.can_to_udp_rules.find(frame.can_id);
        if (it!= m_config.can_to_udp_rules.end()) {
            uint16_t dest_port = it->second;
            auto udp_it = m_udp_channels.find(dest_port);
            if (udp_it!= m_udp_channels.end()) {
                struct sockaddr_in dest_addr{};
                dest_addr.sin_family = AF_INET;
                dest_addr.sin_port = htons(dest_port);
                // MODIFICACIÓN: Usar la IP del host de simulación desde la configuración
                inet_pton(AF_INET, m_config.simulation_host_ip.c_str(), &dest_addr.sin_addr);

                UdpBuffer buffer(frame.data, frame.data + frame.can_dlc);
                udp_it->second->send_to(buffer, dest_addr);
            }
        }
    }
}

void ProtocolGateway::handle_serial_read() {
    SerialBuffer buffer;
    if (m_serial_rx_channel.read(buffer) > 0) {
        const auto& rule = m_config.rs485_to_udp_rule;
        auto udp_it = m_udp_channels.find(rule.dest_port);
        if (udp_it!= m_udp_channels.end()) {
            struct sockaddr_in dest_addr{};
            dest_addr.sin_family = AF_INET;
            dest_addr.sin_port = htons(rule.dest_port);
            // MODIFICACIÓN: Usar la IP del host de simulación desde la configuración
            inet_pton(AF_INET, m_config.simulation_host_ip.c_str(), &dest_addr.sin_addr);
            
            udp_it->second->send_to(buffer, dest_addr);
        }
    }
}

void ProtocolGateway::handle_can_write() {

    auto msg = m_outbound_can_queue->try_pop();
    // auto msg_opt = m_outbound_can_queue->try_pop();
    // if (msg_opt.has_value()) {
    if (msg.has_value()) {

        // AÑADIR ESTE BLOQUE DE DEPURACIÓN
        // const auto& msg = msg_opt.value();
        // std::cout << "DEBUG WRITE DATA: Escribiendo en CAN. ID: 0x" << std::hex << msg.can_id
        //           << std::dec << ", DLC: " << static_cast<int>(msg.can_dlc) << ", Datos: ";
        // for (int i = 0; i < msg.can_dlc; ++i) {
        //     std::cout << std::hex << static_cast<int>(msg.data[i]) << " ";
        // }
        // std::cout << std::dec << std::endl;
        // FIN DEL BLOQUE DE DEPURACIÓN
        m_can_channel.write(msg.value());
        // m_can_channel.write(msg);
    }
}

void ProtocolGateway::handle_serial_write() {
    auto msg = m_outbound_serial_queue->try_pop();
    if (msg.has_value()) {
        m_serial_tx_channel.write(msg.value());
    }
}