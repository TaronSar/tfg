// Server side implementation of UDP client-server model 
#include <bits/stdc++.h> 
#include <stdlib.h> 
#include <unistd.h> 
#include <string.h> 

#include "../include/libstreaming.h"

// Driver code 
int main() { 

    streaming server(20, SERVER);
    server.configure_server(8080);
	server.run_server();
	
	
	return 0; 
}
