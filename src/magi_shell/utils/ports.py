# src/magi_shell/utils/ports.py
"""
Port management utilities for MAGI Shell.
"""

import socket
import psutil
import time

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def find_process_using_port(port):
    """Find process using a specific port"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.connections('tcp'):
                if conn.laddr.port == port:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def release_port(port):
    """Release a port by terminating the process using it"""
    proc = find_process_using_port(port)
    if proc:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
            return True
        except psutil.NoSuchProcess:
            pass
    return False
