#include "Can.h"
#include <bits/stdc++.h>

struct sockaddr_can addr;
struct ifreq ifr;



Can::Can(const std::string& device, Uint32 bitrate){
    this->socket_fd = can_open_port(device.c_str(), bitrate);
	this->device = device;
	this->bitrate = bitrate;
}

Uint8 Can::Write(Buffer buffer){
	struct can_frame frame;
    frame.can_id = buffer.id;
    frame.can_dlc = 8; // TO DO
    memcpy(frame.data, buffer.data, 8);

    Uint8 count = write(socket_fd, &frame, sizeof(struct can_frame));
	if (count != sizeof(struct can_frame)) {
        printf("CAN write error (result %d, valued expected %d)\n", count, sizeof(struct can_frame));
		return -1;
	}

    return count;
}

Uint8 Can::Read(Buffer& buffer){
    struct can_frame frame;

	Uint8 nbytes = read(socket_fd, &frame, sizeof(struct can_frame));
    
    if (nbytes < 0) {
        printf("CAN read error\n");
        return 1;
    }

    memcpy(buffer.data, frame.data, nbytes);
    buffer.id = frame.can_id;

    return nbytes;
}



Can::~Can(){
    std::string sys_cmd;
///
    sys_cmd = "ip link set " + this->device + " down";
///
    if(system(sys_cmd.c_str()) < 0){
        printf("Error - Unable to close CAN.\n");
    }  
	if (close(this->socket_fd) < 0) {
		perror("Close");
	}

}


Uint32 Can::can_open_port(const char *device, Uint32 bitrate) {
    std::string sys_cmd;
    Uint32 fd;
    

    sys_cmd = "ip link set " + std::string(device) + " type can bitrate " + std::to_string(bitrate) + " restart-ms " + std::to_string(restart_time);
    if(system(sys_cmd.c_str()) < 0){
        printf("Error - Unable to open CAN. Device not found or bitrate not valid\n");
		return 1;
    }
    sys_cmd = "ip link set " + std::string(device) + " up";
    if(system(sys_cmd.c_str()) < 0){
        printf("Error - Unable to open CAN. Unable to set up interface\n");
		return 1;
    }    

	if ((fd = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0) {
		perror("Socket");
		return 1;
	}
	strcpy(ifr.ifr_name, device);
	ioctl(fd, SIOCGIFINDEX, &ifr);

	memset(&addr, 0, sizeof(addr));
	addr.can_family = AF_CAN;
	addr.can_ifindex = ifr.ifr_ifindex;

	if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
		perror("Bind");

		return 1;
	}


    return fd;
}


