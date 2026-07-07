import socket
import binascii

def udp_hex_listener(port, max_buffer_size=4096):
    """
    Listens to a UDP port and displays received data in hexadecimal format
    
    Args:
        port (int): UDP port to listen on
        max_buffer_size (int): Maximum receive buffer size
    """
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', port))
        
        print(f"Listening on UDP port {port}. Press Ctrl+C to stop...")
        print("=" * 60)
        
        while True:
            # Receive data
            data, addr = sock.recvfrom(max_buffer_size)
            
            # Display connection information
            print(f"\nPacket received from {addr[0]}:{addr[1]}")
            print(f"Length: {len(data)} bytes")
            
            # Convert to hexadecimal
            hex_data = binascii.hexlify(data).decode('ascii')
            
            # Format hexadecimal output
            formatted_hex = ' '.join([hex_data[i:i+2] for i in range(0, len(hex_data), 2)])
            
            print("Data in hexadecimal:")
            print(formatted_hex)
            
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        sock.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Listen to a UDP port and display data in hexadecimal')
    parser.add_argument('port', type=int, help='UDP port to listen on')
    parser.add_argument('--buffer', type=int, default=4096, 
                       help='Receive buffer size (default: 4096)')
    
    args = parser.parse_args()
    
    udp_hex_listener(args.port, args.buffer)