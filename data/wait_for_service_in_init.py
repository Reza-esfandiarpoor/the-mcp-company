import os
import socket
import time

while True:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((os.environ.get("SERVER_HOSTNAME", "localhost"), 6379))
    if result != 0:
        print("Waiting for redis server to respond.")
        time.sleep(1)
    else:
        print("Redis server is ready")
        break
