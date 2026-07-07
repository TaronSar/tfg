#include <Udp_server.h>
#include <Can.h>
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
    Can can_dev("can0", 1000000);
    server.client("192.168.1.156");
    
    while(1)
    {
        Can::Buffer can_buff;
        can_dev.Read(can_buff);
        printf("Received can frame id: %d\n", can_buff.id);

        for(int i = 0; i < 8; i++)
        {
            buffs.at(can_buff.id - 2000).out_buff.push_back(can_buff.data[i]); // TO DO some relation between ports and can id and port
        }

        server.send();
    }

    return 0;
}