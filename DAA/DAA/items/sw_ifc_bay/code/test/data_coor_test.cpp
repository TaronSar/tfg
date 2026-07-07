#include <Udp_server.h>
#include <Serial_port.h>
#include <Can.h>
#include <iostream>
#include <vector>
#include <unistd.h>
#include <map> // Necesario para el mapa de búsqueda

// --- Definición de puertos ---
#define RS485_PORT_START 2000
#define RS485_PORT_END   2010
#define CAN_PORT_START   2011
#define NUM_CAN_PORTS    15 
#define CAN_PORT_END     (CAN_PORT_START + NUM_CAN_PORTS - 1)
#define RS485_RX_FIXED_PORT 2000 
#define CLIENT_IP "192.168.1.150"
#define MSG_SIZE 16 // TO DO

// --- Prototipos de funciones ---
void eth_to_rs485(Serial_port& rs485_tx, Udp_server::Port_buffer& p_buff);
void eth_to_can(Can& can, Udp_server::Port_buffer& p_buff);
// Modificamos las funciones para usar el mapa y hacerlas más eficientes
void can_to_eth(Can& can_dev, std::vector<Udp_server::Port_buffer>& buffs, std::map<Uint16, size_t>& port_map);
void rs485_to_eth(Serial_port& rs485_rx, std::vector<Udp_server::Port_buffer>& buffs, std::map<Uint16, size_t>& port_map);


int main() {
    
    std::vector<Udp_server::Port_buffer> buffs;

    // Mapa para buscar el índice de un puerto de forma instantánea: Puerto -> Índice
    std::map<Uint16, size_t> port_to_idx_map;

    // Añadir puertos RS485
    for (int port = RS485_PORT_START; port <= RS485_PORT_END; ++port) {
        Udp_server::Port_buffer p_buff;
        p_buff.port = port;
        p_buff.size = MSG_SIZE; // TO DO
        buffs.push_back(p_buff);
        port_to_idx_map[port] = buffs.size() - 1;
    }
    // Añadir puertos CAN
    for (int port = CAN_PORT_START; port <= CAN_PORT_END; ++port) {
        Udp_server::Port_buffer p_buff;
        p_buff.port = port;
        p_buff.size = MSG_SIZE; // TO DO
        buffs.push_back(p_buff);
        port_to_idx_map[port] = buffs.size() - 1;
    }

    Udp_server server(buffs);
    Serial_port rs485_tx("/dev/ttyUL2", B115200);
    Serial_port rs485_rx("/dev/ttyUL1", B115200);
    Can can_dev_0("can0", 1000000);

    server.client(CLIENT_IP);
    std::cout << "Data Coordinator NO-BLOQUEANTE iniciado." << std::endl;

    // --- Bucle Principal NO-BLOQUEANTE ---
    while(1) {
        // 1. Comprobar UDP 
        // printf("DEBUG: Flag 1 - Antes de Get Polled de UDP\n"); fflush(stdout);
        int polled_idx = server.get_polled(); // Devuelve -1 si no hay nada
        // printf("DEBUG: Flag 2 - Después de Get Polled de UDP\n"); fflush(stdout);
        if (polled_idx != -1) {
            Uint16 port = buffs.at(polled_idx).port;
            if (port >= CAN_PORT_START && port <= CAN_PORT_END) {
                // printf("DEBUG: Flag 3 - Antes de enviar a CAN\n"); fflush(stdout);
                eth_to_can(can_dev_0, buffs.at(polled_idx));
                // printf("DEBUG: Flag 4 - Después de enviar a CAN\n"); fflush(stdout);
            } else if (port >= RS485_PORT_START && port <= RS485_PORT_END) {
                // printf("DEBUG: Flag 5 - Antes de enviar a RS485\n"); fflush(stdout);
                eth_to_rs485(rs485_tx, buffs.at(polled_idx));
                // printf("DEBUG: Flag 6 - Después de enviar a RS485\n"); fflush(stdout);
            }
        }

        // 2. Comprobar Periféricos
        // printf("DEBUG: Flag 7 - Antes de escuchar a CAN\n"); fflush(stdout);
        can_to_eth(can_dev_0, buffs, port_to_idx_map);
        // printf("DEBUG: Flag 8 - Después de escuchar a CAN y antes de RS485\n"); fflush(stdout);
        rs485_to_eth(rs485_rx, buffs, port_to_idx_map);
        // printf("DEBUG: Flag 9 - Después de escuchar a RS485\n"); fflush(stdout);

        // 3. Enviar lo que se haya preparado
        // printf("DEBUG: Flag 10 - Antes de enviar todo por UDP\n"); fflush(stdout);
        server.send();
        // printf("DEBUG: Flag 11 - Después de enviar todo por UDP\n"); fflush(stdout);

        // Pausa muy corta para no consumir 100% de CPU pero mantener alta reactividad
        usleep(500); // 0.5 ms
    }
    return 0;
}

// --- Implementación de las funciones ---

void eth_to_rs485(Serial_port& rs485_tx, Udp_server::Port_buffer& p_buff) {
    std::vector<Uint8> out_buff;
    out_buff.push_back((Uint8)(p_buff.port >> 8) & 0xFF);
    out_buff.push_back((Uint8)p_buff.port & 0xFF);
    out_buff.insert(out_buff.end(), p_buff.in_buff.begin(), p_buff.in_buff.end());
    printf("ETH (Puerto %d) -> RS485 (con cabecera)\n", p_buff.port);
    rs485_tx.Write(out_buff);
}

void eth_to_can(Can& can, Udp_server::Port_buffer& p_buff) {
    Can::Buffer can_buff;
    can_buff.id = p_buff.port;
    // size_t len = std::min((size_t)p_buff.in_buff.size(), (size_t)8);  // TO DO dynamic
    // std::copy(p_buff.in_buff.begin(), p_buff.in_buff.begin() + len, can_buff.data);
    can_buff.data = p_buff.in_buff;
    printf("ETH -> CAN (ID %d)\n", can_buff.id);
    printf("[ETH->CAN] Tamaño de p_buff.in_buff: %zu\n", p_buff.in_buff.size()); fflush(stdout);
    can.Write(can_buff);
}

// MODIFICADO para usar el mapa de búsqueda
void can_to_eth(Can& can_dev, std::vector<Udp_server::Port_buffer>& buffs, std::map<Uint16, size_t>& port_map) {
    Can::Buffer can_in_buff;
    // printf("DEBUG: Flag 7.1 - Antes de Read()\n"); fflush(stdout);
    if (can_dev.Read(can_in_buff) > 0) {
        // Buscamos el puerto en el mapa
        // printf("DEBUG: Flag 7.2 - Dentro de Read()\n"); fflush(stdout);
        auto it = port_map.find(can_in_buff.id);
        if (it != port_map.end()) { // Si se encuentra el puerto
            size_t idx = it->second; // Obtenemos el índice directamente
            printf("CAN -> ETH (ID %d)\n", can_in_buff.id);
            printf("[CAN->ETH] Tamaño de can_in_buff.data: %zu\n", can_in_buff.data.size()); fflush(stdout);
            // buffs[idx].out_buff.assign(can_in_buff.data, can_in_buff.data + 8);  // TO DO dynamic
            buffs[idx].out_buff = can_in_buff.data;
        }
    }
}

// MODIFICADO para usar el mapa de búsqueda
void rs485_to_eth(Serial_port& rs485_rx, std::vector<Udp_server::Port_buffer>& buffs, std::map<Uint16, size_t>& port_map) {
    // printf("DEBUG: Flag 8.1 - Antes de Available\n"); fflush(stdout);
    if (rs485_rx.Available() > 0) {
        // printf("DEBUG: Flag 8.2 - Después de Available\n"); fflush(stdout);
        std::vector<Uint8> serial_buff;
        rs485_rx.Read(serial_buff);
        // printf("DEBUG: Flag 8.3 - Después de READ\n"); fflush(stdout);

        // Buscamos el puerto fijo en el mapa
        if (!serial_buff.empty()) {
            // printf("DEBUG: Flag 8.4 - Después de empty\n"); fflush(stdout);
            auto it = port_map.find(RS485_RX_FIXED_PORT);
            if (it != port_map.end()) {
                size_t idx = it->second;
                printf("RS485 (Punto a Punto) -> ETH (Puerto %d)\n", RS485_RX_FIXED_PORT);
                buffs[idx].out_buff = serial_buff;
            }
        }
    }
}