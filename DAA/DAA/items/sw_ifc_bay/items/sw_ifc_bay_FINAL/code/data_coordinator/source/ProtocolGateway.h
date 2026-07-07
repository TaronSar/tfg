#pragma once

#include "PollingEngine.h"
#include "channels/CanChannel.h"
#include "channels/SerialChannel.h"
#include "channels/UdpChannel.h"
#include "utils/ThreadSafeQueue.h"

#include <string>
#include <vector>
#include <memory>
#include <atomic>
#include <map>

// La estructura de configuración ahora incluye la IP del host de simulación.
struct AppConfig {
    std::string simulation_host_ip; // IP única para el host de simulación
    std::string can_interface_name;
    
    struct SerialConfig {
        std::string device;
        unsigned int baud_rate;
    };
    SerialConfig serial_rx;
    SerialConfig serial_tx;

    size_t queue_size;
    std::vector<uint16_t> udp_ports;

    std::map<uint16_t, canid_t> udp_to_can_rules;
    std::map<canid_t, uint16_t> can_to_udp_rules;
    uint16_t udp_to_rs485_port;
    struct {
        uint16_t dest_port;
    } rs485_to_udp_rule;
};

class ProtocolGateway {
public:
    explicit ProtocolGateway(AppConfig config);
    ~ProtocolGateway();

    ProtocolGateway(const ProtocolGateway&) = delete;
    ProtocolGateway& operator=(const ProtocolGateway&) = delete;

    void run();
    void stop();

private:
    bool setup_channels();

    // --- Manejadores de eventos para el PollingEngine ---
    void handle_can_read();
    void handle_serial_read();
    void handle_udp_read(uint16_t port); // Ahora recibe el puerto como argumento

    void handle_can_write();
    void handle_serial_write();
    
    // Bucle que se ejecuta en el hilo principal para gestionar la escritura
    void main_loop_logic();

    AppConfig m_config;
    PollingEngine m_polling_engine;
    std::atomic<bool> m_shutdown_flag;

    CanChannel m_can_channel;
    SerialChannel m_serial_rx_channel;
    SerialChannel m_serial_tx_channel;
    std::map<uint16_t, std::unique_ptr<UdpChannel>> m_udp_channels;

    std::unique_ptr<MessageQueue<CanMessage>> m_outbound_can_queue;
    std::unique_ptr<MessageQueue<SerialBuffer>> m_outbound_serial_queue;
};