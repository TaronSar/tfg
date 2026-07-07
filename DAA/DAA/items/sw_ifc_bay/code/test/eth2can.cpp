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

    
    while(1)
    {
        Uint16 port_polled_idx = server.get_polled();
        if(port_polled_idx >= 0)
        {

            Can::Buffer can_buff;
            can_buff.id = buffs.at(port_polled_idx).port;

            for(int i = 0; i < buffs.at(port_polled_idx).size; i++)
            {
                printf(" x%02X", buffs.at(port_polled_idx).in_buff.at(i));
                can_buff.data[i] = buffs.at(port_polled_idx).in_buff.at(i);
            }
            can_dev.Write(can_buff);
            usleep(1000);
            printf("\n");
        }
    }

    return 0;
}