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


    
    while(1)
    {
        Uint16 port_polled_idx = server.get_polled();
        if(port_polled_idx >= 0)
        {
            std::vector<Uint8> data2ser;
            data2ser.push_back((Uint8)(buffs.at(port_polled_idx).port >> 8) & 0xFF);
            data2ser.push_back((Uint8)buffs.at(port_polled_idx).port & 0xFF);

            for(int i = 0; i < buffs.at(port_polled_idx).size; i++)
            {
                printf(" x%02X", buffs.at(port_polled_idx).in_buff.at(i));
                data2ser.push_back(buffs.at(port_polled_idx).in_buff.at(i));
            }
            rs485.Write(data2ser);
            usleep(1000);
            printf("\n");
        }
    }

    return 0;
}