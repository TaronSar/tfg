

extern "C"{
	#include <stdlib.h>
	#include <fcntl.h>
	#include <stdio.h>
	#include <math.h>
	#include <time.h>
	#include <unistd.h>
	#include <unistd.h>
}

#include <vector>
#include <stdint.h>
#include <bits/stdc++.h> 
#include <stdlib.h> 
#include <unistd.h> 
#include <string.h> 
#include <sys/types.h> 
#include <sys/socket.h> 
#include <arpa/inet.h> 
#include <netinet/in.h> 

#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs.hpp>


extern "C"{
    #include <stdio.h>
    #include <stdlib.h>

}

typedef enum {
    SERVER = 0,
    CLIENT = 1
} streaming_role;


class streaming
{
        const int max_buffer_size = 65535; //bytes
        const int compression_quality = 50; //0-100
	private:
        int framerate;
        streaming_role role;
	
	public:

    streaming(int fr, streaming_role s_role);
    int configure_server(int port);
    void run_server();
    int configure_client(const char* server_ip_address, int port);
    int send_frame(cv::Mat frame);

};


