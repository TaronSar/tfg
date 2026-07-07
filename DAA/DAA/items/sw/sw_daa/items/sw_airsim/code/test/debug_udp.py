#!/usr/bin/env python3
"""
Debug UDP connectivity for OPS bridge.
"""

import socket
import subprocess
from loguru import logger

# check_port_listening will check if local port 56777 is listening.
def check_port_listening():
    logger.info("=== Checking if port 56777 is listening ===")
    try:
        result = subprocess.run(
            ["netstat", "-tlun"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "56777" in result.stdout:
            logger.info("Port 56777 is listening")
            logger.info(result.stdout)
        else:
            logger.error("Port 56777 is NOT listening")
            logger.info("Current listening ports:")
            logger.info(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("⚠ netstat command not available, trying ss command...")
        try:
            result = subprocess.run(
                ["ss", "-tlun"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "56777" in result.stdout:
                logger.info("Port 56777 is listening")
            else:
                logger.error("Port 56777 is NOT listening")
            logger.info(result.stdout)
        except FileNotFoundError:
            logger.warning("⚠ No port checking tools available (netstat/ss)")

# check_network_interfaces will show available network interfaces and their IP addresses.
def check_network_interfaces():
    logger.info("=== Network Interfaces ===")
    try:
        result = subprocess.run(
            ["ip", "addr"],
            capture_output=True,
            text=True,
            timeout=5
        )
        logger.info(result.stdout)
    except FileNotFoundError:
        logger.warning("'ip' command not available")
        try:
            result = subprocess.run(
                ["ifconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )
            logger.info(result.stdout)
        except FileNotFoundError:
            logger.warning("No network tools available (ip/ifconfig)")
            logger.info("Attempting to detect hostname and localhost...")
            import socket
            try:
                hostname = socket.gethostname()
                localhost_ip = socket.gethostbyname(hostname)
                logger.info(f"Hostname: {hostname}")
                logger.info(f"Localhost IP: {localhost_ip}")
                logger.info("127.0.0.1 is available (loopback)")
            except Exception as e:
                logger.error(f"Could not detect network info: {e}")

# test_socket_binding will try to bind to port 56777.
def test_socket_binding():
    logger.info("=== Testing local socket binding ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("0.0.0.0", 56777))
        logger.info("Successfully bound to 0.0.0.0:56777")
        sock.close()
    except OSError as e:
        logger.error(f"Failed to bind to 0.0.0.0:56777: {e}")
        logger.info("  This port may already be in use by another bridge instance")

# test_remote_connectivity will test if we can send to the remote OPS.
def test_remote_connectivity():
    logger.info("=== Testing connectivity to remote OPS (127.0.0.1:12345) ===")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.settimeout(1.0)
        
        # Try sending a test packet
        test_data = b"TEST_PACKET"
        sock.sendto(test_data, ("127.0.0.1", 12345))
        logger.info("Successfully sent test packet to 127.0.0.1:12345")
        
        # Try receiving (expect timeout)
        try:
            data, addr = sock.recvfrom(1024)
            logger.info(f"Received response from {addr}: {data[:50]}")
        except socket.timeout:
            logger.warning("No response received (expected if OPS not running)")
        
        sock.close()
    except Exception as e:
        logger.error(f"Failed to communicate: {e}")

# show_bridge_config will show the current bridge configuration.
def show_bridge_config():
    logger.info("=== Current Bridge Configuration ===")
    logger.info("Local:  0.0.0.0:56777 (receives from OPS)")
    logger.info("Remote: 127.0.0.1:12345 (sends to OPS)")
    logger.info("To change configuration, you can:")
    logger.info("1. Modify verontesil_ownship_writer.py line ~103")
    logger.info("   self._ops_usb_bridge = OPSUsbUdpBridge()")
    logger.info("   to:")
    logger.info("   self._ops_usb_bridge = OPSUsbUdpBridge(")
    logger.info('       local_ip="0.0.0.0",')
    logger.info('       local_port=56777,')
    logger.info('       remote_ip="<OPS_IP>",')
    logger.info('       remote_port=<OPS_PORT>')
    logger.info("   )")

def main():
    logger.info("=" * 60)
    logger.info("UDP Bridge Debugging Tool")
    logger.info("=" * 60)
    
    check_network_interfaces()
    check_port_listening()
    test_socket_binding()
    test_remote_connectivity()
    show_bridge_config()
    
    logger.info("\n" + "=" * 60)
    logger.info("Debugging Complete")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
