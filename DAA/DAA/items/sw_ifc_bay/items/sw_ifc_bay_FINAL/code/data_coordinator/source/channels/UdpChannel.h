#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <netinet/in.h>

using UdpBuffer = std::vector<uint8_t>;

class UdpChannel {
public:
    UdpChannel() = default;
    ~UdpChannel();

    UdpChannel(const UdpChannel&) = delete;
    UdpChannel& operator=(const UdpChannel&) = delete;

    /**
     * @brief Abre un socket UDP y lo vincula a un puerto local.
     * @param port El puerto en el que escuchar. Si es 0, el sistema operativo asignará uno.
     * @return true si la apertura fue exitosa, false en caso contrario.
     */
    bool open(uint16_t port);

    /**
     * @brief Cierra el socket UDP.
     */
    void close();

    /**
     * @brief Envía datos a un destino específico.
     * @param buffer El buffer de datos a enviar.
     * @param dest_addr La estructura de dirección del destino.
     * @return true si el envío fue exitoso, false en caso contrario.
     */
    bool send_to(const UdpBuffer& buffer, const struct sockaddr_in& dest_addr);

    /**
     * @brief Recibe datos, almacenando la dirección del remitente.
     * @param buffer Buffer donde se almacenarán los datos recibidos.
     * @param src_addr Estructura donde se almacenará la dirección del remitente.
     * @return El número de bytes recibidos, o -1 en caso de error.
     */
    ssize_t receive_from(UdpBuffer& buffer, struct sockaddr_in& src_addr);

    /**
     * @brief Obtiene el descriptor de archivo del socket para usarlo con poll().
     * @return El descriptor de archivo, o -1 si el socket no está abierto.
     */
    int get_file_descriptor() const { return m_socket; }

private:
    int m_socket = -1;
};