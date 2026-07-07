#ifndef UDP_SERVER_H
#define UDP_SERVER_H

#include <string>
#include <cstring>
#include <arpa/inet.h>
#include <unistd.h>
#include <stdexcept>
#include <vector>
#include <errno.h>
#include <unistd.h>
#include <poll.h>

//Vlibs
#include <Entypes.h>


class Udp_server {
public:

    typedef struct{
        Uint16 polled;
        Uint16 port;
        Uint16 size;
        std::vector<Uint8> in_buff;
        std::vector<Uint8> out_buff;
    } Port_buffer; 

    Udp_server(std::vector<Port_buffer>& p_buffs);  
    ~Udp_server();        

    Uint16 get_polled();
    Uint16 send();
    Uint8 client(const std::string& address);

private:    

    std::vector<Port_buffer>* p_buffers;
    std::vector<struct pollfd> fds;
    struct sockaddr_in servaddr;
    std::string client_addr;

    Uint32 create_socket(Uint16 port);
    Uint16 receive_data(Uint32 socket, Uint16 size, std::vector<Uint8>& buffer);
    Uint8 send_data(Uint32 fdesc, Uint16 port, std::vector<Uint8>& buffer);

};

#endif