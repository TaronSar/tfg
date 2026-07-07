
#ifndef CAN_H
#define CAN_H

#include <stdio.h>
#include <unistd.h>			
#include <fcntl.h>			
#include <termios.h>		
#include <string>
#include <queue>
#include <stdio.h>
#include <iostream>
#include <mutex>
#include <vector>

#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>

#include <linux/can.h>
#include <linux/can/raw.h>
#include <linux/can/error.h>

#include <Entypes.h>
//#include <semaphore>

//#define DEBUG

class Can{
public:
    typedef struct{
        Uint16 id;
        Uint8 data[8]; //TO DO change to dynamic
    } Buffer;

    static const Uint32 restart_time = 1; //ms

    Can(const std::string& device, Uint32 bitrate);
    Uint8 Write(Buffer buffer); //
    Uint8 Read(Buffer& buffer); //
    ~Can();
    

private:

    Uint32 can_open_port(const char *device, Uint32 bitrate);

    Uint32 socket_fd;
    std::string device;
    Uint32 bitrate;
};

#endif