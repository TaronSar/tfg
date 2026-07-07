#include "Serial_port.h"
#include <iostream>
#include <unistd.h>
#include <vector>

int main() {
    try {
        // Abrimos el puerto de recepción que nos da problemas
        Serial_port rs485_rx("/dev/ttyUL1", B115200);
        std::cout << "Puerto /dev/ttyUL1 abierto. Escuchando datos..." << std::endl;

        while (true) {
            int bytes_count = rs485_rx.Available();

            if (bytes_count > 0) {
                std::cout << "¡Datos detectados! Bytes disponibles: " << bytes_count << std::endl;

                std::vector<Uint8> read_buffer;
                ssize_t bytes_read = rs485_rx.Read(read_buffer);

                if (bytes_read > 0) {
                    std::cout << "Leídos " << bytes_read << " bytes: '";
                    // Imprimir como texto
                    for (size_t i = 0; i < read_buffer.size(); ++i) {
                        std::cout << static_cast<char>(read_buffer[i]);
                    }
                    std::cout << "'" << std::endl;
                }
            }

            // Dormir un poco para no saturar la CPU
            usleep(200000); // 200 ms
        }

    } catch (const std::runtime_error& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}