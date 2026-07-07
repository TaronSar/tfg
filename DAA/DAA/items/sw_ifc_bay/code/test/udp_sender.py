import socket
import sys
import random
import time

if len(sys.argv) != 3:
    print("Usage: python3 udp_sender.py <ip_address> <port>")
    sys.exit(1)

target_ip = sys.argv[1]

try:
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Open file in binary mode and read all content

    while True:
        port = int(sys.argv[2]) + random.randint(0, 19)

        if port % 2 == 0:
            data = bytes([j % 256 for j in range(0,8)])
        else:
            data = bytes([j % 256 for j in range(8,0)])

        # Send all data in one UDP packet
        sock.sendto(data, (target_ip, port))

        print("Sent to " + hex(port) + " " + str(data))
        time.sleep(0.01)
        
    
    
except Exception as e:
    print(f"Unexpected error: {str(e)}")
finally:
    sock.close()