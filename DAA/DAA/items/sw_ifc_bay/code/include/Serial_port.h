#include <string>
#include <stdexcept>
#include <cstring>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>

#include <vector>

#include <Entypes.h>

class Serial_port {
public:
    Serial_port(const std::string& device, int baudrate) ;
    ~Serial_port() ;
    void Close();

    Uint8 Write(std::vector<Uint8> buffer);
    Uint8 Read(std::vector<Uint8>& buffer);

private:
    void Open(const std::string& device, int baudrate);
    bool IsOpen();
    Uint32 Available();
    Uint32 fd;
};