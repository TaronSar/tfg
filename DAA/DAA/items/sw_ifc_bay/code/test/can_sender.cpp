#include <Udp_server.h>
#include <Can.h>
#include <iostream>

int main() {
    
    Can can_dev("can0", 1000000);

    
    int port = 2000;
    while(1)
    {
        printf("SENT\n");
        Can::Buffer can_buff;
        can_buff.id = port;
        for(int i = 0; i < 8; i++)
        {
            can_buff.data[i] = 0x5A + (port - 2000) + i;
        }
        can_dev.Write(can_buff);
        usleep(1000000);
        port++;
        if(port > 2020) port = 0;
    }

    return 0;
}