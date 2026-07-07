#include "ProtocolGateway.h"
#include "nlohmann/json.hpp"
#include <iostream>
#include <fstream>
#include <csignal>
#include <memory>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <cstdlib> // Para la función system()

using json = nlohmann::json;

// Puntero global al gateway para poder detenerlo desde el manejador de señal.
std::unique_ptr<ProtocolGateway> gateway_ptr = nullptr;

void signal_handler(int signum) {
    std::cout << "\nSeñal de interrupción (" << signum << ") recibida. Deteniendo el gateway..." << std::endl;
    if (gateway_ptr) {
        gateway_ptr->stop();
    }
}

// Función para cargar la configuración desde el archivo JSON.
bool load_config(const std::string& path, AppConfig& config) {
    std::ifstream f(path);
    if (!f.is_open()) {
        std::cerr << "Error: No se pudo abrir el archivo de configuración: " << path << std::endl;
        return false;
    }

    try {
        json data = json::parse(f);

        config.simulation_host_ip = data.at("simulation_host_ip").get<std::string>();
        config.can_interface_name = data.at("can_interface").get<std::string>();
        
        const auto& serial_conf = data.at("serial_config");
        config.serial_rx.device = serial_conf.at("rx_port").at("device").get<std::string>();
        config.serial_rx.baud_rate = serial_conf.at("rx_port").at("baud_rate").get<unsigned int>();
        config.serial_tx.device = serial_conf.at("tx_port").at("device").get<std::string>();
        config.serial_tx.baud_rate = serial_conf.at("tx_port").at("baud_rate").get<unsigned int>();

        config.queue_size = data.at("queue_size").get<size_t>();
        config.udp_ports = data.at("udp_ports").get<std::vector<uint16_t>>();

        // Cargar reglas de enrutamiento
        const auto& rules = data.at("routing_rules");
        for (const auto& rule : rules.at("udp_to_can")) {
            uint16_t port = rule.at("udp_port").get<uint16_t>();
            canid_t can_id = std::stoul(rule.at("can_id").get<std::string>(), nullptr, 16);
            config.udp_to_can_rules[port] = can_id;
        }
        for (const auto& rule : rules.at("can_to_udp")) {
            canid_t can_id = std::stoul(rule.at("can_id").get<std::string>(), nullptr, 16);
            uint16_t port = rule.at("udp_port").get<uint16_t>();
            config.can_to_udp_rules[can_id] = port;
        }
        
        config.udp_to_rs485_port = rules.at("udp_to_rs485").at("udp_port").get<uint16_t>();
        config.rs485_to_udp_rule.dest_port = rules.at("rs485_to_udp").at("udp_port").get<uint16_t>();
        // La IP de destino se toma del campo global
        //config.rs485_to_udp_rule.dest_address = config.simulation_host_ip;

    } catch (json::exception& e) {
        std::cerr << "Error al parsear el JSON: " << e.what() << std::endl;
        return false;
    }

    return true;
}

// --- Funciones de ayuda para GPIO ---
// Exporta un pin GPIO para que sea accesible desde sysfs
int gpio_export(int pin) {
    char buf[64];
    int fd = open("/sys/class/gpio/export", O_WRONLY);
    if (fd < 0) {
        perror("Error abriendo /sys/class/gpio/export");
        return -1;
    }
    snprintf(buf, sizeof(buf), "%d", pin);
    write(fd, buf, strlen(buf));
    close(fd);
    return 0;
}

// Configura la dirección del GPIO (in/out)
int gpio_set_dir(int pin, const char *dir) {
    char buf[128];
    snprintf(buf, sizeof(buf), "/sys/class/gpio/gpio%d/direction", pin);
    int fd = open(buf, O_WRONLY);
    if (fd < 0) {
        perror("Error abriendo dirección de GPIO");
        return -1;
    }
    write(fd, dir, strlen(dir));
    close(fd);
    return 0;
}

// Escribe un valor en el GPIO (0 o 1)
int gpio_set_value(int pin, int value) {
    char path_buf[128];
    char val_buf[8];
    snprintf(path_buf, sizeof(path_buf), "/sys/class/gpio/gpio%d/value", pin);
    int fd = open(path_buf, O_WRONLY);
    if (fd < 0) {
        perror("Error abriendo valor de GPIO");
        return -1;
    }
    snprintf(val_buf, sizeof(val_buf), "%d", value);
    write(fd, val_buf, strlen(val_buf));
    close(fd);
    return 0;
}

// Ejecuta un comando de la shell y avisa si hay un error, pero no detiene el programa.
void execute_command(const std::string& command) {
    std::cout << "Ejecutando: " << command << std::endl;
    int result = system(command.c_str());
    if (result != 0) {
        std::cerr << "Advertencia: El comando '" << command << "' devolvió un error. "
                  << "Esto puede ser normal si la interfaz ya estaba configurada o no existe. Continuando..." << std::endl;
    }
}

int main() {
    int gpio_pin_UL1 = 416;
    if (gpio_export(gpio_pin_UL1) < 0 || gpio_set_dir(gpio_pin_UL1, "out") < 0) {
        fprintf(stderr, "Fallo al configurar GPIO para UL1\n");
        return -1;
    }
    gpio_set_value(gpio_pin_UL1, 0); // Escucha

    int gpio_pin_UL2 = 417;
    if (gpio_export(gpio_pin_UL2) < 0 || gpio_set_dir(gpio_pin_UL2, "out") < 0) {
        fprintf(stderr, "Fallo al configurar GPIO para UL2\n");
        return -1;
    }
    gpio_set_value(gpio_pin_UL2, 1); // Habla

    execute_command("ip link set can0 up type can bitrate 1000000");
    execute_command("ip link set can1 up type can bitrate 1000000");

    // Registrar manejador para señales de interrupción (Ctrl+C)
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    std::cout << "Iniciando el Coordinador de Datos..." << std::endl;

    AppConfig config;
    if (!load_config("config/config.json", config)) {
        return 1;
    }

    std::cout << "Configuración cargada correctamente." << std::endl;

    gateway_ptr = std::make_unique<ProtocolGateway>(std::move(config));
    
    // run() es una llamada bloqueante que iniciará todos los hilos y bucles.
    gateway_ptr->run();

    std::cout << "El Coordinador de Datos se ha detenido." << std::endl;

    execute_command("ip link set can0 down");
    execute_command("ip link set can1 down");

    return 0;
}