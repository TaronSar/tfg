#include "Udp_server.h"
#include <iostream>
#include <vector>


Udp_server::Udp_server(std::vector<Port_buffer>& p_buffs) {

    for(Uint16 i = 0; i < p_buffs.size() ; i++)
    {
        p_buffs.at(i).in_buff.resize(p_buffs.at(i).size);

        struct pollfd socket_fd;
        socket_fd.fd = create_socket(p_buffs.at(i).port);
        socket_fd.events = POLLIN;
        socket_fd.revents = 0;

        fds.push_back(socket_fd);
    }
    p_buffers = &p_buffs;
    
}

Udp_server::~Udp_server() {
   
}

Uint16 Udp_server::get_polled()
{
    bool polled = false;
    Uint16 polled_idx = -1;

    do {
        Uint32 ret = poll(fds.data(), fds.size(), 1000);
        if (ret < 0) {
            printf("poll failed\n");
            break;
        } else if (ret == 0) {
            // Timeout
            continue;
        }
        
        for(Uint16 i = 0; i < fds.size() ; i++)
        {
            if (fds.at(i).revents & POLLIN) {  
                Uint16 s_recv = receive_data(fds.at(i).fd, p_buffers->at(i).size, p_buffers->at(i).in_buff);
                polled = true;
                polled_idx = i;
            }
        }

    } while(!polled);
    return polled_idx;
}

Uint8 Udp_server::client(const std::string& address)
{
    client_addr = address;
    return 0;
}

Uint16 Udp_server::send()
{ 
    Uint16 sents = 0;
    for(Uint16 i = 0; i < p_buffers->size(); i++)
    {
        if(p_buffers->at(i).out_buff.size() > 0)
        {
            send_data(fds.at(i).fd, p_buffers->at(i).port, p_buffers->at(i).out_buff);
            sents++;
        }
    }
    return sents;
}




Uint32 Udp_server::create_socket(Uint16 port)
{
    // Crear socket UDP
    Uint32 sockfd;
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0) {
        throw std::runtime_error("Error creating socket UDP");
    }

    memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_addr.s_addr = INADDR_ANY; // Escuchar en todas las interfaces
    servaddr.sin_port = htons(port);


    if (bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0) {
        throw std::runtime_error("Error linking socket to port");
    }
    return sockfd;
}


Uint16 Udp_server::receive_data(Uint32 fdesc, Uint16 size, std::vector<Uint8>& buffer) {
    struct sockaddr_in cliaddr;
    socklen_t len = sizeof(cliaddr);
    Uint16 n = recvfrom(fdesc, buffer.data(), size, 0, (struct sockaddr *)&cliaddr, &len);
    if (n < 0) {
        throw std::runtime_error("Error receiving data");
    }
    
    return n;
}

Uint8 Udp_server::send_data(Uint32 fdesc, Uint16 port, std::vector<Uint8>& buffer) {
    struct sockaddr_in cliaddr;

    // Configurar la dirección del servidor
    cliaddr.sin_family = AF_INET;
    cliaddr.sin_port = htons(port);

    if (inet_pton(AF_INET, client_addr.c_str(), &cliaddr.sin_addr) <= 0) {
        throw std::runtime_error("Wrong client address");
    }
    socklen_t len = sizeof(cliaddr);
    printf("Sending %d bytes\n", buffer.size());
    Uint16 n = sendto(fdesc, buffer.data(), buffer.size(), 0, (struct sockaddr *)&cliaddr, sizeof(cliaddr));
    buffer.clear();

    if (n < 0) {
        throw std::runtime_error("Error sending data");
    }

    return (n);
}