#pragma once

#include <string>
#include <linux/can.h> // Para struct can_frame

//Revisar como vmm6 configuraba el bitrate desde aquí

// Alias para la estructura de la trama CAN para mayor claridad.
using CanMessage = struct can_frame;

class CanChannel {
public:
    CanChannel() = default;
    ~CanChannel();

    // Prohíbe la copia para evitar duplicados de sockets.
    CanChannel(const CanChannel&) = delete;
    CanChannel& operator=(const CanChannel&) = delete;

    /**
     * @brief Abre y vincula un socket a una interfaz CAN específica.
     * @param interface_name El nombre de la interfaz (ej. "can0", "vcan0").
     * @return true si la apertura fue exitosa, false en caso contrario.
     */
    bool open(const std::string& interface_name);

    /**
     * @brief Cierra el socket CAN si está abierto.
     */
    void close();

    /**
     * @brief Escribe una trama CAN en el bus.
     * @param frame La trama CAN a enviar.
     * @return true si la escritura fue exitosa, false en caso contrario.
     */
    bool write(const CanMessage& frame);

    /**
     * @brief Lee una trama CAN del bus. Esta es una llamada bloqueante si no se usa
     *        con un mecanismo de sondeo como poll().
     * @param frame Referencia a la estructura donde se almacenará la trama leída.
     * @return true si la lectura fue exitosa, false en caso contrario.
     */
    bool read(CanMessage& frame);

    /**
     * @brief Obtiene el descriptor de archivo del socket para usarlo con poll().
     * @return El descriptor de archivo, o -1 si el socket no está abierto.
     */
    int get_file_descriptor() const { return m_socket; }

private:
    int m_socket = -1;
};