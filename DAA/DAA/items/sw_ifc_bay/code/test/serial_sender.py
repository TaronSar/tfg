#!/usr/bin/env python
# -*- coding: utf-8 -*-

import serial
import time

# Serial port configuration
PORT = '/dev/ttyUSB1'
BAUDRATE = 115200
TIMEOUT = 1  # seconds

# Hardcoded byte frame (example)
# Modify this according to your needs
BYTE_FRAME = bytes([
    0x07,  # Start byte
    0xD0,  # Command
    0x02, 
    0x03,  # Data
    0x55,  # End byte
    0x02, 
    0x03,  # Data
    0x55,  # End byte
    0x03,  # Data
    0x55  # End byte
])

def send_frame():
    try:
        # Open serial port
        with serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT) as ser:
            print(f"Connected to {PORT} at {BAUDRATE} baud")
            
            # Send frame
            print(f"Sending frame: {BYTE_FRAME.hex(' ').upper()}")
            ser.write(BYTE_FRAME)
            
            # Small delay to ensure transmission
            time.sleep(0.1)
            
            print("Frame sent successfully")
            
            # Optional: Read response if expected
            # response = ser.read(ser.in_waiting or 1)
            # if response:
            #     print(f"Received response: {response.hex(' ').upper()}")
            
    except serial.SerialException as e:
        print(f"Serial communication error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    send_frame()