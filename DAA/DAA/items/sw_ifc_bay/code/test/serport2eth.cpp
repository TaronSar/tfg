#include <Udp_server.h>
#include <Serial_port.h>
#include <iostream>

int main() {
    
    std::vector<Udp_server::Port_buffer> buffs;

    Udp_server::Port_buffer test;
    test.size = 8;

    for(int i = 0; i < 20; i++)
    {
        test.port = 2000 + i;
        buffs.push_back(test);
    }

    Udp_server server(buffs);
    Serial_port rs485("/dev/ttyPS0", B115200);
    server.client("192.168.1.156");
    
    while(1)
    {
        std::vector<Uint8> data_buff;
        rs485.Read(data_buff);
        printf("Received serial frame\n");

        for(int i = 0; i < data_buff.size(); i++)
        {
            buffs.at(0).out_buff.push_back(data_buff[i]); // TO DO some relation between ports and can id and port
        }

        server.send();
    }

    return 0;
}