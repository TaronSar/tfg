#include <can_hil.h>

Can_hil::Can_hil(const std::string& device, int bitrate) : Can(device, bitrate, false, false){
}

void Can_hil::ReadPose(double& latitude, double& longitude, double& altitude, float& roll, float& pitch, float& yaw, float& vx, float& vy, float& vz, bool& fix, bool& execution)
{
    unsigned char response[can_frame_size];  
    unsigned char recv_buffer[8];
    int can_id, buff_idx, resp_idx, header_size = 0;
    bool start_frame = false, end_frame = false;
    int buff_length;
    uint64_t latitude_64;
    uint64_t longitude_64;
    uint64_t altitude_64;
    uint32_t roll_32;
    uint32_t pitch_32;
    uint32_t yaw_32;
    uint32_t vx_32;
    uint32_t vy_32;
    uint32_t vz_32;

    buff_idx = 0;
    resp_idx = 0;
    
    do{
        Read(recv_buffer, &buff_length, &can_id);
        header_size = 0;

        if(!start_frame && recv_buffer[0] == 0x5A){
            start_frame = true;
            header_size = 1;
        }

        if(start_frame){
            int i = 0;
            //Byte assignation and reordenation
            for(; i < (buff_length - header_size); i++){
                if((resp_idx + i) < can_frame_size) //to avoid stack smashing error
                {
                    *(uint8_t*)(response + resp_idx + i) = *(uint8_t*)(recv_buffer + i + header_size);
                }
            }
            resp_idx += i; 
            
        }
        else{
            resp_idx = 0;
            start_frame = false;
        }
        if(resp_idx >= (can_frame_size-1) && response[can_frame_size-1] == 0xAA){
            end_frame = true;
            std::cout << "correct" <<std::endl;
        }
        else if(resp_idx > (can_frame_size-1)){
            
            resp_idx = 0;
            start_frame = false;
            std::cout << "fail" <<std::endl;
        }
        
    }while(!end_frame);

        

    reset_wbuff();

    latitude_64     = ((uint64_t*)response)[0];
    longitude_64    = ((uint64_t*)response)[1];
    altitude_64      = ((uint64_t*)response)[2];
    roll_32        = ((uint32_t*)response)[6];
    pitch_32       = ((uint32_t*)response)[7];
    yaw_32         = ((uint32_t*)response)[8];
    vx_32             = ((uint32_t*)response)[9];
    vy_32              = ((uint32_t*)response)[10];
    vz_32              = ((uint32_t*)response)[11];

    execution      = (bool)(((uint8_t*)response)[(can_frame_size-2)] & 0x02);
    fix      = (bool)(((uint8_t*)response)[(can_frame_size-2)] & 0x01);
//
//
    latitude    = *((double*)&latitude_64);
    longitude    = *((double*)&longitude_64);
    
    altitude     = *((double*)&altitude_64);
    roll        = *((float*)&roll_32);
    pitch       = *((float*)&pitch_32);
    yaw         = *((float*)&yaw_32);
    vx        = *((float*)&vx_32);
    vy       = *((float*)&vy_32);
    vz         = *((float*)&vz_32);
}

void Can_hil::WritePose(double latitude, double longitude, double altitude, float roll, float pitch, float yaw, float timestamp, int shs, bool fix, bool execution){
    
    unsigned char package[50];
    unsigned char send_pkg[8];

    int pending_bytes;

    uint64_t latitude_64;
    uint64_t longitude_64;
    uint64_t altitude_64;
    uint32_t roll_32;
    uint32_t pitch_32;
    uint32_t yaw_32;
    uint32_t timestamp_32;
    uint32_t shs_32;

    // Reinterpret cast uintX_t
    *((double*)&latitude_64) = latitude;
    *((double*)&longitude_64) = longitude;
    *((double*)&altitude_64) = altitude;
    *((float*)&roll_32) = roll;
    *((float*)&pitch_32) = pitch;
    *((float*)&yaw_32) = yaw;
    *((float*)&timestamp_32) = timestamp;
    *((int*)&shs_32) = shs;

    // Filling array 
    *((uint8_t*)package + 1) = 0xAA;
    ((uint64_t*)(package + 2))[0] = latitude_64;
    ((uint64_t*)(package + 2))[1] = longitude_64;
    ((uint64_t*)(package + 2))[2] = altitude_64;  
    // ((uint32_t*)(package + 2))[6] = roll_32;
    // ((uint32_t*)(package + 2))[7] = pitch_32;
    // ((uint32_t*)(package + 2))[8] = yaw_32; 
    // ((uint32_t*)(package + 2))[9] = timestamp_32;
    // ((uint32_t*)(package + 2))[10] = shs_32;
    memcpy(package + 26, &roll,       sizeof(float));   // [26–29]
    memcpy(package + 30, &pitch,      sizeof(float));   // [30–33]
    memcpy(package + 34, &yaw,        sizeof(float));   // [34–37]
    memcpy(package + 38, &timestamp,  sizeof(float));   // [38–41]
    memcpy(package + 42, &shs,        sizeof(int));     // [42–45]
    ((uint8_t*)(package))[46] = (fix? 0x80 : 0x00);
    ((uint8_t*)(package))[46] |= (execution? 0x40 : 0x00);
    ((uint8_t*)(package))[47] = 0x00;
    ((uint8_t*)(package))[48] = 0x00;
    ((uint8_t*)(package))[49] = 0x5A;

    // Spliting array in 8 bytes packages to be sended
    pending_bytes = 49;
    for(int i = 0; i < 7; i++){
        *((uint64_t*)(send_pkg)) = *(uint64_t*)(package + (i * 7));
        //Counter to reconstruct the array at 1xVeronte
        send_pkg[0] = pkg_cnt;
        if(pending_bytes >= 7) Write(send_pkg, 8, Can::can_id_rd);
        else  Write(send_pkg, pending_bytes + 1, Can::can_id_rd);
        pending_bytes -= 7;
        pkg_cnt++;
        usleep(10);
    }
    

}

