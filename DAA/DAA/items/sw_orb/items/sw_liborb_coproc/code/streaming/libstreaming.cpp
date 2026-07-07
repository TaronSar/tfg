#include "libstreaming.h"
#include <sys/select.h>
#include <Stlvector.h>

// Constructor implementation
streaming::streaming(int fr, streaming_role s_role) :
	framerate(fr),
	role(s_role),
	sockfd(-1)
{
	memset(&servaddr, 0, sizeof(servaddr));
    memset(&cliaddr, 0, sizeof(cliaddr));
}

int streaming::configure_server(int port){
 
	
    if(role != SERVER) return 1;

	// Creating socket file descriptor 
	if ( (sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0 ) { 
		perror("socket creation failed"); 
		exit(EXIT_FAILURE); 
	} 
	
	memset(&servaddr, 0, sizeof(servaddr)); 
	memset(&cliaddr, 0, sizeof(cliaddr)); 
	
	// Filling server information 
	servaddr.sin_family = AF_INET; // IPv4 
	servaddr.sin_addr.s_addr = INADDR_ANY; 
	servaddr.sin_port = htons(port); 
	
	// Bind the socket with the server address 
	if (bind(sockfd, (const struct sockaddr *)&servaddr, sizeof(servaddr)) < 0 ) 
	{ 
		perror("bind failed"); 
		exit(EXIT_FAILURE); 
	} 

	return 0;
}



int streaming::configure_client(const char* server_ip_address, int port){
 
	
    if(role != CLIENT) return 1;
	
	// Create UDP socket
	if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
		perror("socket creation failed\n");
		return false;
	}

    memset(&servaddr, 0, sizeof(servaddr)); 
		
    servaddr.sin_family = AF_INET; 
    servaddr.sin_port = htons(port); 
    servaddr.sin_addr.s_addr = inet_addr(server_ip_address); 
	

	return 0;
}

void streaming::close_socket()
{
	if (sockfd >= 0)
	{
		close(sockfd);
		sockfd = -1;
	}
}


int streaming::send_frame(cv::Mat frame){
 
	std::vector<uchar> buf;
	std::vector<int> params;
	
	params.push_back(cv::IMWRITE_JPEG_QUALITY);
	params.push_back(compression_quality);

	if(frame.empty()) return -1;

	if (!cv::imencode(".jpg", frame, buf, params)) {
		std::cout << "JPEG compression failed.\n";
	}

	if (!sendto(sockfd, (const uchar*)buf.data(), buf.size(), MSG_DONTWAIT, (const struct sockaddr*)&servaddr, sizeof(servaddr))) {
		std::cout << "Failed to send frame to server.\n";
	}

	return buf.size();
}

void streaming::run_server(){
	cv::Mat img_array = cv::Mat::zeros(1, max_buffer_size, CV_8U);
    cv::Mat image_mat;
    long long frame_time;
	char buffer[max_buffer_size]; 
    int n;
	socklen_t len;
	std::chrono::_V2::system_clock::time_point init, end;
	std::chrono::milliseconds duration;
	int sleep_time;
    while(true){

   		init = std::chrono::high_resolution_clock::now();
	    n = recvfrom(sockfd, (char *)buffer, max_buffer_size, MSG_WAITALL, ( struct sockaddr *) &cliaddr, &len); 
	    buffer[n] = '\0'; 
		for (size_t i = 0; i < n; ++i) {
        	img_array.at<uchar>(0,i) = static_cast<uchar>(buffer[i]);
    	}
		image_mat = cv::imdecode(img_array, (int)cv::IMREAD_COLOR);
		if(image_mat.data != NULL){
    		cv::imshow("Decoded Image", image_mat);
		}
		else{
			std::cout << "Non-valid frame" << std::endl;
		}
	 	end = std::chrono::high_resolution_clock::now();
		duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - init);
   		frame_time = duration.count();
		//std::cout << "Bytes received: " << n << std::endl;
		sleep_time = (int)((1000/framerate)-frame_time);
		if(sleep_time > 0){
			cv::waitKey(sleep_time);  	
		}
		else{
			cv::waitKey(1);  
		}
		
    }
}


bool streaming::handshake_client()
{
	if (role != CLIENT)
	{
		return -1;
	}

	bool hs_done = false;
	char buf[1024];
	int attempts = 0;
    const int max_attempts = 10;
	const char* init_msg = "init handshake";
	const char* ack_msg = "ack handshake";
    socklen_t len = sizeof(servaddr);

	while (!hs_done && attempts < max_attempts)
	{
		int sent = sendto(sockfd, init_msg, strlen(init_msg), 0,
                          (struct sockaddr *)&servaddr, sizeof(servaddr));

        // Wait for response (timeout 1 sec)
        fd_set readfds;
        FD_ZERO(&readfds);
        FD_SET(sockfd, &readfds);
        struct timeval tv;
        tv.tv_sec = 1;
        tv.tv_usec = 0;

        int activity = select(sockfd + 1, &readfds, NULL, NULL, &tv);
        if (activity > 0 && FD_ISSET(sockfd, &readfds))
		{
            int n = recvfrom(sockfd, buf, sizeof(buf) - 1, 0, NULL, NULL);
            if (n > 0)
			{
                buf[n] = '\0';
                if (strcmp(buf, ack_msg) == 0)
				{
                    hs_done = true;
                    break;
                }
            }
        }
		std::cout << "Waiting for server connection..." << std::endl;
        attempts++;
        sleep(1); // Retry after 1 sec
	}

	return hs_done;
}

bool streaming::handshake_server()
{
	if (role != SERVER)
	{
		return -1;
	}

	bool hs_done = false;
	char buf[1024];
	const char* init_msg = "init handshake";
	const char* ack_msg = "ack handshake";
    socklen_t len = sizeof(cliaddr);

	while (!hs_done)
	{
		fd_set readfds;
		FD_ZERO(&readfds);
		FD_SET(sockfd, &readfds);
		struct timeval tv;
		tv.tv_sec = 1;
		tv.tv_usec = 0;
		
		int activity = select(sockfd + 1, &readfds, NULL, NULL, &tv);

		if (activity > 0 && FD_ISSET(sockfd, &readfds))
		{
			int n = recvfrom(sockfd, buf, sizeof(buf) - 1, 0,
								(struct sockaddr *)&cliaddr, &len);
			if (n > 0)
			{
				buf[n] = '\0';
				if (strcmp(buf, init_msg) == 0)
				{
					// Answer with ACK message
					int sent = sendto(sockfd, ack_msg, strlen(ack_msg), 0,
										(struct sockaddr *)&cliaddr, len);
					if (sent > 0)
					{
						hs_done = true;
					}
				}
			}
		}
		else
		{
			// If message is not received yet, keep waiting.
			std::cout << "Waiting for client connection..." << std::endl;
		}
	}
	return hs_done;
}


int streaming::receive_request(void* buffer)
{
	if (role != SERVER)
	{
		return -1;
	}
	socklen_t len = sizeof(cliaddr);
	return recvfrom(sockfd, (char *)buffer, max_buffer_size, MSG_WAITALL, ( struct sockaddr *) &cliaddr, &len);
}

int streaming::send_request(const void* buffer)
{
	if (role != CLIENT)
	{
		return -1;
	}
	return sendto(sockfd, (const uchar*)buffer, strlen((char*)buffer), MSG_DONTWAIT, (const struct sockaddr*)&servaddr, sizeof(servaddr));	
}

int streaming::receive_data(void* buffer)
{
	if (role != CLIENT)
	{
		return -1;
	}

	socklen_t len = sizeof(servaddr);
	int n = recvfrom(sockfd, (char *)buffer, max_buffer_size, MSG_WAITALL, ( struct sockaddr *) &servaddr, &len);
	return n;
}

int streaming::send_data(const void* buffer, size_t size)
{
	if (role != SERVER)
	{
		return -1;
	}
	// std::cout << "DENTRO de send_data()" << std::endl;
	// std::cout << "size = " << size << std::endl;

	return sendto(sockfd, (const uchar*)buffer, size, MSG_DONTWAIT, (const struct sockaddr*)&cliaddr, sizeof(cliaddr));	
}


int streaming::send_frame_viewer(cv::Mat frame)
{
	if (role != SERVER)
	{
		return -1;
	}

	std::vector<uchar> buf;
	std::vector<int> params;

	params.push_back(cv::IMWRITE_JPEG_QUALITY);
	params.push_back(compression_quality);

	if(frame.empty()) return -1;

	if (!cv::imencode(".jpg", frame, buf, params)) {
		std::cout << "JPEG compression failed.\n";
	}

	if (!sendto(sockfd, (const uchar*)buf.data(), buf.size(), MSG_DONTWAIT, (const struct sockaddr*)&cliaddr, sizeof(cliaddr))) {
		std::cout << "Failed to send frame to server.\n";
	}

	return buf.size();
}

int streaming::receive_frame(cv::Mat& frame)
{
	if (role != CLIENT)
	{
        return -1;
    }

    char buffer[max_buffer_size];
    socklen_t len = sizeof(servaddr);
    int n = recvfrom(sockfd, buffer, max_buffer_size, MSG_WAITALL, (struct sockaddr*)&servaddr, &len);

    if (n <= 0) {
        std::cerr << "Failed to receive frame or empty frame received.\n";
        return -1;
    }

    // Convert received data into a cv::Mat buffer
	// std::vector<uchar> img_buf(buffer, buffer+n);
	Base::Stlvector<uchar> img_buf(n, Base::Memmgr::external);
	img_buf.resize(n);
	for (Uint32 i = 0; i < img_buf.end(); i++)
	{
		img_buf[i] = buffer[i];
	}

    // cv::Mat img_array(1, n, CV_8U, img_buf);
    // cv::Mat img_array(1, n, CV_8U, img_buf.data());
    cv::Mat img_array(1, n, CV_8U, img_buf.first());

    // Decode the image
	try
	{
		frame = cv::imdecode(img_array, cv::IMREAD_UNCHANGED);
	}
	catch (const cv::Exception& e)
	{
	}

    if (frame.empty()) {
        std::cerr << "Failed to decode received frame.\n";
        return -1;
    }

    return n;  // Return the number of bytes received
}

const int streaming::get_max_buf_size()
{
	return max_buffer_size;
}