#include "Serial_port.h"

Serial_port::Serial_port(const std::string& device, int baudrate) 
        : fd(-1) {
        Open(device, baudrate);
    }

Serial_port::~Serial_port() {
        Close();
    }

void Serial_port::Open(const std::string& device, int baudrate) {
        if (IsOpen()) {
            Close();
        }

        fd = ::open(device.c_str(), O_RDWR | O_NOCTTY | O_NDELAY);
        if (fd == -1) {
            throw std::runtime_error("Failed to open serial port: " + device);
        }

        // Configure serial port
        struct termios options;
        tcgetattr(fd, &options);

        // Baud rate
        cfsetispeed(&options, baudrate);
        cfsetospeed(&options, baudrate);

        // Basic configuration: 8 bits, no parity, 1 stop bit
        options.c_cflag &= ~PARENB;
        options.c_cflag &= ~CSTOPB;
        options.c_cflag &= ~CSIZE;
        options.c_cflag |= CS8;
        options.c_cflag |= (CLOCAL | CREAD);

        // Raw input
        options.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);

        // Disable input processing
        options.c_iflag &= ~(IXON | IXOFF | IXANY);
        options.c_iflag &= ~(INLCR | ICRNL | IGNCR);

        // Raw output
        options.c_oflag &= ~OPOST;
        options.c_oflag &= ~ONLCR;

        // Wait for at least 1 character, no timeout
        options.c_cc[VMIN]  = 1;
        options.c_cc[VTIME] = 0;

        if (tcsetattr(fd, TCSANOW, &options) != 0) {
            ::close(fd);
            fd = -1;
            throw std::runtime_error("Error configuring serial port");
        }

        // Clear buffers
        tcflush(fd, TCIOFLUSH);
    }

void Serial_port::Close() {
        if (IsOpen()) {
            ::close(fd);
            fd = -1;
        }
    }

bool Serial_port::IsOpen() {
    return fd != -1;
}

Uint8 Serial_port::Write(std::vector<Uint8> buffer) {
    if (!IsOpen()) {
        throw std::runtime_error("Serial port not open");
    }
    return write(fd, buffer.data(), buffer.size());
}

Uint8 Serial_port::Read(std::vector<Uint8>& buffer) {
    Uint8 data[256];
    Uint8 data_received = 0;

    if (!IsOpen()) {
        throw std::runtime_error("Serial port not open");
    }
    data_received = read(fd, data, 256);

    buffer.resize(data_received);

    memcpy(buffer.data(), data, data_received);

    return data_received;
}

Uint32 Serial_port::Available() {
    if (!IsOpen()) {
        return 0;
    }
    int bytes;
    ioctl(fd, FIONREAD, &bytes);
    return bytes;
}