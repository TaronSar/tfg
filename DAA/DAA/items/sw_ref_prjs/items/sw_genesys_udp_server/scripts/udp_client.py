from scapy.all import *
import numpy as np
import cv2
import time

# Configuración de la escucha UDP
LISTEN_IP = "192.168.1.20"
SENDER_IP = "192.168.1.10"
LISTEN_PORT = 5001  # Puerto de escucha basado en tcpdump

WIDTH = 960   # Ancho de la imagen en píxeles
HEIGHT = 540  # Alto de la imagen en píxeles

temp_image = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)  # Imagen temporal
current_line = 0  # Índice de la línea actual
start_time = None

def packet_handler(packet):
    global current_line, temp_image, start_time
    
    if packet.haslayer(UDP) and packet[IP].src == SENDER_IP and packet[UDP].sport == LISTEN_PORT:
        data = bytes(packet[UDP].payload)
        
        if len(data) == WIDTH:  # Asegurarse de que sea exactamente una línea de píxeles
            temp_image[current_line, :] = np.frombuffer(data, dtype=np.uint8)
            current_line += 1
            
            if current_line == 1:
                start_time = time.time()
            
            if current_line >= HEIGHT:
                elapsed_time = (time.time() - start_time) * 1000  # Convertir a milisegundos
                print(f"Tiempo de actualización: {elapsed_time:.2f} ms -> {1/(elapsed_time / 1000):.2f} FPS")
                cv2.imshow("Stream UDP", temp_image)
                cv2.waitKey(1)
                current_line = 0  # Reiniciar el índice para la siguiente imagen

print(f"Escuchando en {LISTEN_IP}:{LISTEN_PORT} esperando datos de {SENDER_IP}")
sniff(prn=packet_handler, filter="udp", iface="enp3s0", store=0)
