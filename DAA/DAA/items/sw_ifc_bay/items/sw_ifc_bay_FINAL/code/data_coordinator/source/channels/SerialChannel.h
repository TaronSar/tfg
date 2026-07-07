#pragma once

#include <string>
#include <vector>
#include <cstdint>

// Se eliminan las cabeceras de Boost
// #include <boost/asio.hpp>
// #include <boost/asio/serial_port.hpp>

using SerialBuffer = std::vector<uint8_t>;

class SerialChannel {
public:
    SerialChannel();
    ~SerialChannel();

    SerialChannel(const SerialChannel&) = delete;
    SerialChannel& operator=(const SerialChannel&) = delete;

    /**
     * @brief Abre y configura un puerto serie.
     * @param device La ruta del dispositivo (ej. "/dev/ttyUSB0").
     * @param baud_rate La velocidad en baudios (ej. 115200).
     * @return true si la apertura fue exitosa, false en caso contrario.
     */
    bool open(const std::string& device, unsigned int baud_rate);

    /**
     * @brief Cierra el puerto serie.
     */
    void close();

    /**
     * @brief Escribe datos en el puerto serie.
     * @param buffer El buffer de datos a enviar.
     * @return true si la escritura fue exitosa, false en caso contrario.
     */
    bool write(const SerialBuffer& buffer);

    /**
     * @brief Lee los datos disponibles en el puerto serie sin bloquear.
     * @param buffer Buffer donde se almacenarán los datos leídos.
     * @return El número de bytes leídos, o -1 en caso de error.
     */
    ssize_t read(SerialBuffer& buffer);

    /**
     * @brief Obtiene el descriptor de archivo nativo para usarlo con poll().
     * @return El descriptor de archivo nativo.
     */
    int get_native_handle();

private:
    // Se reemplazan los objetos de Boost por un descriptor de archivo (file descriptor).
    int m_fd = -1;
    int m_fa = -1;
};