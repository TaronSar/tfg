#include "UdpChannel.h"
#include <iostream>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <arpa/inet.h>

UdpChannel::~UdpChannel() {
    close();
}

void UdpChannel::close() {
    if (m_socket!= -1) {
        ::close(m_socket);
        m_socket = -1;
    }
}

bool UdpChannel::open(uint16_t port) {
    if ((m_socket = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Error al crear el socket UDP");
        return false;
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));

    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = htonl(INADDR_ANY); // Escuchar en todas las interfaces
    serv_addr.sin_port = htons(port);

    if (bind(m_socket, (const struct sockaddr*)&serv_addr, sizeof(serv_addr)) < 0) {
        perror("Error al vincular el socket UDP");
        close();
        return false;
    }

    std::cout << "Canal UDP escuchando en el puerto " << port << std::endl;
    return true;
}

bool UdpChannel::send_to(const UdpBuffer& buffer, const struct sockaddr_in& dest_addr) {
    if (m_socket == -1) return false;

    ssize_t bytes_sent = ::sendto(m_socket, buffer.data(), buffer.size(), 0,
                                  (const struct sockaddr*)&dest_addr, sizeof(dest_addr));

    if (bytes_sent < 0) {
        perror("Error en sendto() UDP");
        return false;
    }
    if (static_cast<size_t>(bytes_sent)!= buffer.size()) {
        std::cerr << "Error: No se enviaron todos los bytes del datagrama UDP" << std::endl;
        return false;
    }
    return true;
}

ssize_t UdpChannel::receive_from(UdpBuffer& buffer, struct sockaddr_in& src_addr) {
    if (m_socket == -1) return -1;

    buffer.resize(65535); 

    socklen_t addr_len = sizeof(src_addr);
    
    ssize_t bytes_received = ::recvfrom(m_socket, buffer.data(), buffer.size(), 0,
                                        (struct sockaddr*)&src_addr, &addr_len);

    if (bytes_received < 0) {
        perror("Error en recvfrom() UDP");
        buffer.resize(0); // Si hay error, vaciamos el buffer.
        return -1;
    }

    buffer.resize(bytes_received); 
    
    return bytes_received;
}