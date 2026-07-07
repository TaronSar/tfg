#include <Udp_server.h>
#include <Serial_port.h>
#include <Can.h>
#include <iostream>

#define BASE_PORT 2000

void rs485_send(Serial_port rs485, Udp_server::Port_buffer in_buff);
void can_send(Can can, Udp_server::Port_buffer in_buff);

int main() {
    
    std::vector<Udp_server::Port_buffer> buffs;

    Udp_server::Port_buffer test;
    test.size = 8;

    for(int i = 0; i < 20; i++)
    {
        test.port = BASE_PORT + i;
        buffs.push_back(test);
    }

    Udp_server server(buffs);
    Serial_port rs485("/dev/ttyPS0", B115200);
    Can can_dev("can0", 1000000);


    
    while(1)
    {
        Uint16 port_polled_idx = server.get_polled();
        if(port_polled_idx >= 0)
        {
            if( buffs.at(port_polled_idx).port > BASE_PORT + 10)
            {
                can_send(can_dev, buffs.at(port_polled_idx));
            }
            else
            {
                rs485_send(rs485, buffs.at(port_polled_idx));
            }
        }
    }

    return 0;
}

void rs485_send(Serial_port rs485, Udp_server::Port_buffer in_buff)
{
    std::vector<Uint8> out_buff;
    
    out_buff.push_back((Uint8)(in_buff.port >> 8) & 0xFF);
    out_buff.push_back((Uint8)in_buff.port & 0xFF);
    
    for(int i = 0; i < in_buff.in_buff.size(); i++)
    {
        printf(" x%02X", in_buff.in_buff.at(i));
        out_buff.push_back(in_buff.in_buff.at(i));
    }

    rs485.Write(out_buff);

}



void can_send(Can can, Udp_server::Port_buffer in_buff)
{    
    Can::Buffer can_buff;
    can_buff.id = in_buff.port;

    for(int i = 0; i < in_buff.size; i++)
    {
        printf(" x%02X", in_buff.in_buff.at(i));
        can_buff.data[i] = in_buff.in_buff.at(i);
    }
    can.Write(can_buff);
}