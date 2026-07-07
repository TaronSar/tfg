#include "CanChannel.h"
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>

CanChannel::~CanChannel() {
    close();
}

void CanChannel::close() {
    if (m_socket!= -1) {
        ::close(m_socket);
        m_socket = -1;
    }
}

bool CanChannel::open(const std::string& interface_name) {
    // Crear el socket
    if ((m_socket = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) {
        perror("Error al crear el socket CAN");
        return false;
    }

    // Especificar la interfaz CAN
    struct sockaddr_can addr;
    struct ifreq ifr;

    std::strncpy(ifr.ifr_name, interface_name.c_str(), IFNAMSIZ - 1);
    //ifr.ifr_name = '\0';
    ifr.ifr_name[IFNAMSIZ - 1] = '\0';
    if (ioctl(m_socket, SIOCGIFINDEX, &ifr) < 0) {
        perror("Error en ioctl al obtener el índice de la interfaz CAN");
        close();
        return false;
    }

    // Vincular el socket a la interfaz CAN
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(m_socket, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("Error al vincular el socket CAN");
        close();
        return false;
    }

    std::cout << "Canal CAN abierto en la interfaz " << interface_name << std::endl;
    return true;
}

bool CanChannel::write(const CanMessage& frame) {
    if (m_socket == -1) return false;
    
    ssize_t bytes_written = ::write(m_socket, &frame, sizeof(CanMessage));
    if (bytes_written!= sizeof(CanMessage)) {
        perror("Error al escribir en el socket CAN");
        return false;
    }
    return true;
}

bool CanChannel::read(CanMessage& frame) {
    if (m_socket == -1) return false;

    ssize_t bytes_read = ::read(m_socket, &frame, sizeof(CanMessage));
    if (bytes_read < 0) {
        perror("Error al leer del socket CAN");
        return false;
    }
    if (bytes_read < sizeof(CanMessage)) {
        std::cerr << "Error: Lectura de trama CAN incompleta" << std::endl;
        return false;
    }
    return true;
}