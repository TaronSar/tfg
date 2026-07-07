#include "SerialChannel.h"
#include <iostream>
#include <unistd.h>  // Para open, close, read, write
#include <fcntl.h>   // Para O_RDWR, O_NOCTTY
#include <termios.h> // Para la configuración del puerto serie
#include <cstring>   // Para strerror
#include <cerrno>    // Para errno

SerialChannel::SerialChannel() : m_fd(-1) {}

SerialChannel::~SerialChannel() {
    close();
}

void SerialChannel::close() {
    if (m_fd != -1) {
        ::close(m_fd);
        m_fd = -1;
    }
}

bool SerialChannel::open(const std::string& device, unsigned int baud_rate) {
    // Abrir el dispositivo serie
    m_fd = ::open(device.c_str(), O_RDWR | O_NOCTTY);
    if (m_fd == -1) {
        std::cerr << "Error al abrir el puerto serie " << device << ": " << strerror(errno) << std::endl;
        return false;
    }

    // Configurar opciones del puerto con termios
    struct termios tty;
    if (tcgetattr(m_fd, &tty) != 0) {
        std::cerr << "Error al obtener atributos del puerto serie: " << strerror(errno) << std::endl;
        close();
        return false;
    }

    // Configurar velocidad (baud rate)
    speed_t speed;
    switch (baud_rate) {
        case 9600:   speed = B9600;   break;
        case 19200:  speed = B19200;  break;
        case 38400:  speed = B38400;  break;
        case 57600:  speed = B57600;  break;
        case 115200: speed = B115200; break;
        default:
            std::cerr << "Velocidad de " << baud_rate << " no soportada." << std::endl;
            close();
            return false;
    }
    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);

    // Configuración estándar (8N1)
    tty.c_cflag &= ~PARENB; // Sin paridad
    tty.c_cflag &= ~CSTOPB; // 1 stop bit
    tty.c_cflag &= ~CSIZE;  // Limpiar bits de tamaño de caracter
    tty.c_cflag |= CS8;     // 8 data bits
    tty.c_cflag &= ~CRTSCTS;// Sin control de flujo por hardware
    tty.c_cflag |= CREAD | CLOCAL; // Habilitar lectura y ignorar señales de control del módem

    // Configurar modo "raw" (no canónico) para procesar byte a byte
    tty.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);
    tty.c_oflag &= ~OPOST; // Sin procesamiento de salida

    // Configurar comportamiento de read() para que sea no bloqueante
    // VMIN = 0, VTIME = 0: read() retorna inmediatamente con los bytes disponibles.
    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 0;

    // Aplicar la configuración
    if (tcsetattr(m_fd, TCSANOW, &tty) != 0) {
        std::cerr << "Error al configurar el puerto serie: " << strerror(errno) << std::endl;
        close();
        return false;
    }

    std::cout << "Canal Serie abierto en " << device << " a " << baud_rate << " baudios." << std::endl;
    return true;
}

bool SerialChannel::write(const SerialBuffer& buffer) {
    if (m_fd == -1) return false;

    ssize_t bytes_written = ::write(m_fd, buffer.data(), buffer.size());
    if (bytes_written == -1) {
        std::cerr << "Error al escribir en el puerto serie: " << strerror(errno) << std::endl;
        return false;
    }
    // Opcional: verificar si se escribieron todos los bytes
    if (static_cast<size_t>(bytes_written) != buffer.size()) {
        std::cerr << "Advertencia: No se escribieron todos los bytes." << std::endl;
        // Podrías manejar una escritura parcial aquí si es necesario
    }
    
    return true;
}

ssize_t SerialChannel::read(SerialBuffer& buffer) {
    if (m_fd == -1) return -1;

    // Usar un buffer temporal para la lectura
    uint8_t temp_buf[1024];
    ssize_t bytes_read = ::read(m_fd, temp_buf, sizeof(temp_buf));

    if (bytes_read < 0) {
        // En modo no bloqueante, EAGAIN o EWOULDBLOCK no son errores fatales
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return 0; // No hay datos disponibles
        }
        std::cerr << "Error al leer del puerto serie: " << strerror(errno) << std::endl;
        return -1; // Error real
    }

    // Copiar los datos leídos al buffer de salida
    buffer.assign(temp_buf, temp_buf + bytes_read);

    return bytes_read;
}

int SerialChannel::get_native_handle() {
    return m_fd;
}