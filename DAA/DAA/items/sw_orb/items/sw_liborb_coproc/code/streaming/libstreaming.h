#ifndef __LIB_STREAMING__
#define __LIB_STREAMING__

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
        int sockfd;
        struct sockaddr_in servaddr, cliaddr; 

	public:

    streaming(int fr, streaming_role s_role);
    int configure_server(int port);
    void run_server();
    int configure_client(const char* server_ip_address, int port);
    void close_socket();
    int send_frame(cv::Mat frame);
    bool handshake_client();
    bool handshake_server();
    int receive_request(void* buffer);
    int send_request(const void* buffer);
    int receive_data(void* buffer);
    int send_data(const void* buffer, size_t size);
    int send_frame_viewer(cv::Mat frame);
    int receive_frame(cv::Mat& frame);
    const int get_max_buf_size();

};

#endif // __LIB_STREAMING__


