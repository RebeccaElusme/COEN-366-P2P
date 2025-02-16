import socket
import json

# Server Configuration
SERVER_IP = "127.0.0.1"  # Server IP (localhost for testing)
SERVER_UDP_PORT = 5000  # UDP Port

# Store registered users
registered_clients = {}

def process_registration(data, client_address):
    """Handles the REGISTER request."""
    name = data["name"]

    if name in registered_clients:
        response = {"type": "REGISTER-DENIED", "reason": "Name already in use"}
    else:
        registered_clients[name] = client_address
        response = {"type": "REGISTERED", "name": name}
    
    return response

def process_deregistration(data):
    """Handles the DE-REGISTER request."""
    name = data["name"]
    
    if name in registered_clients:
        del registered_clients[name]
        response = {"type": "DE-REGISTERED"}
    else:
        response = {"type": "DE-REGISTER-FAILED", "reason": "User not registered"}
    
    return response

def start_server():
    """Starts the UDP server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP, SERVER_UDP_PORT))
    print(f"Server listening on {SERVER_IP}:{SERVER_UDP_PORT}...")

    while True:
        message, client_address = server_socket.recvfrom(1024)
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

# Run server
if __name__ == "__main__":
    start_server()
