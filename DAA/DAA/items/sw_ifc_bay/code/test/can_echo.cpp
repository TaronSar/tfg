#include <Udp_server.h>
#include <Can.h>
#include <iostream>

int main() {
    
    Can can_dev("can0", 1000000);

    
    while(1)
    {

        Can::Buffer can_buff;

        can_dev.Read(can_buff);
        can_buff.id = can_buff.id - 0x100;
        can_dev.Write(can_buff);
        usleep(1000);
        printf("\n");
        
    }

    return 0;
}