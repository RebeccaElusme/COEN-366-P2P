import socket
import json
import threading

# Server Configuration
SERVER_IP = "127.0.0.1"  # Server IP (localhost for testing)
SERVER_UDP_PORT = 5000  # UDP Port
SERVER_TCP_PORT = 6000  # TCP Port for purchase finalization

# Store registered users
registered_clients = {}
lock = threading.Lock()

def process_registration(data, client_address):
    """Handles the REGISTER request."""
    name = data["name"]
    role = data["role"]
    udp_port = data["udp_port"]
    tcp_port = data["tcp_port"]
    
    with lock:
        if name in registered_clients:
            response = {"type": "REGISTER-DENIED", "reason": "Name already in use"}
        else:
            registered_clients[name] = {
                "role": role,
                "ip": client_address[0],
                "udp_port": udp_port,
                "tcp_port": tcp_port
            }
            response = {"type": "REGISTERED", "name": name}
    
    return response

def process_deregistration(data):
    """Handles the DE-REGISTER request."""
    name = data["name"]
    
    with lock:
        if name in registered_clients:
            del registered_clients[name]
            response = {"type": "DE-REGISTERED"}
        else:
            response = {"type": "DE-REGISTER-FAILED", "reason": "User not registered"}
    
    return response

def handle_client(message, client_address, server_socket):
    """Handles client messages in a separate thread."""
    try:
        data = json.loads(message.decode())
        print(f"Received message from {client_address}: {data}")

        if data["type"] == "REGISTER":
            response = process_registration(data, client_address)
        elif data["type"] == "DE-REGISTER":
            response = process_deregistration(data)
        else:
            response = {"type": "ERROR", "reason": "Invalid request"}

        server_socket.sendto(json.dumps(response).encode(), client_address)
    except json.JSONDecodeError:
        print("Error decoding JSON message")

def start_udp_server():
    """Starts the UDP server with multithreading support."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP, SERVER_UDP_PORT))
    print(f"UDP Server listening on {SERVER_IP}:{SERVER_UDP_PORT}...")

    while True:
        message, client_address = server_socket.recvfrom(1024)
        threading.Thread(target=handle_client, args=(message, client_address, server_socket)).start()

def start_tcp_server():
    """Starts the TCP server for purchase finalization."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, SERVER_TCP_PORT))
    server_socket.listen(5)
    print(f"TCP Server listening on {SERVER_IP}:{SERVER_TCP_PORT}...")

    while True:
        client_socket, client_address = server_socket.accept()
        threading.Thread(target=handle_tcp_client, args=(client_socket, client_address)).start()

def handle_tcp_client(client_socket, client_address):
    """Handles TCP client messages for purchase finalization."""
    try:
        data = client_socket.recv(1024).decode()
        print(f"Received TCP message from {client_address}: {data}")
        response = {"type": "PURCHASE-CONFIRMATION", "message": "Purchase finalized successfully."}
        client_socket.send(json.dumps(response).encode())
    except json.JSONDecodeError:
        print("Error decoding JSON message")
    finally:
        client_socket.close()

# Run server
if __name__ == "__main__":
    threading.Thread(target=start_udp_server).start()
    threading.Thread(target=start_tcp_server).start()
