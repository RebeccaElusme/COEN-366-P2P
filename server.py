import socket
import json
import threading
import sys
import re
import os
from datetime import datetime

# Server Configuration
SERVER_IP = "127.0.0.1"
SERVER_UDP_PORT = 5000
REGISTERED_CLIENTS_FILE = "registered_clients.json"

# Store registered users
lock = threading.Lock()

def log_message(message):
    """Logs messages with timestamps."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def load_registered_clients():
    """Loads registered clients from a file on server startup."""
    if os.path.exists(REGISTERED_CLIENTS_FILE):
        with open(REGISTERED_CLIENTS_FILE, "r") as file:
            return json.load(file)
    return {}

def save_registered_clients():
    """Saves registered clients to a file."""
    with open(REGISTERED_CLIENTS_FILE, "w") as file:
        json.dump(registered_clients, file)

registered_clients = load_registered_clients()

def process_registration(data, client_address):
    """Handles the REGISTER request with validation."""
    name = data["name"].strip()
    role = data["role"].strip().capitalize()
    ip = data["ip"]  # Ensure this is received
    udp_port = data["udp_port"]
    rq_number = data.get("rq#", 0)

    if not name or not re.match(r"^[A-Za-z]+$", name):
        return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Invalid name"}

    if role not in ["Buyer", "Seller"]:
        return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Invalid role"}

    with lock:
        if name in registered_clients:
            return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Name already in use"}
        registered_clients[name] = {
            "name": name, "role": role, "ip": ip,
            "udp_port": udp_port, "rq#": rq_number
        }
        save_registered_clients()
        return {"type": "REGISTERED", "rq#": rq_number}

def process_deregistration(data):
    """Handles the DE-REGISTER request."""
    name = data["name"]
    rq_number = data.get("rq#", 0)

    with lock:
        if name in registered_clients:
            del registered_clients[name]
            save_registered_clients()
            return {"type": "DE-REGISTERED", "rq#": rq_number}
        return {"type": "ERROR", "rq#": rq_number, "reason": "User not registered"}

def get_registered_clients():
    """Returns the list of registered clients."""
    with lock:
        return {"type": "CLIENT-LIST", "clients": list(registered_clients.values())}

def handle_client(message, client_address, server_socket):
    """Handles client messages in a separate thread."""
    try:
        data = json.loads(message.decode())
        log_message(f"Received message from {client_address}: {data}")

        if data["type"] == "REGISTER":
            response = process_registration(data, client_address)
        elif data["type"] == "DE-REGISTER":
            response = process_deregistration(data)
        elif data["type"] == "SHOW-CLIENTS":
            response = get_registered_clients()
        else:
            response = {"type": "ERROR", "rq#": data.get("rq#", 0), "reason": "Invalid request"}

        log_message(f"Sending response to {client_address}: {response}")  # DEBUG
        server_socket.sendto(json.dumps(response).encode(), client_address)
    except (json.JSONDecodeError, ConnectionResetError):
        log_message(f"Error handling request from {client_address}")

def start_udp_server(stop_event):
    """Starts the UDP server with multithreading support."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP, SERVER_UDP_PORT))
    log_message(f"UDP Server listening on {SERVER_IP}:{SERVER_UDP_PORT}...")

    try:
        while not stop_event.is_set():
            server_socket.settimeout(1)
            try:
                message, client_address = server_socket.recvfrom(1024)
                threading.Thread(target=handle_client, args=(message, client_address, server_socket)).start()
            except socket.timeout:
                continue
    finally:
        server_socket.close()

def shutdown_server():
    """Handles server shutdown and cleanup."""
    log_message("Shutting down server...")
    stop_event.set()
    save_registered_clients()
    udp_thread.join()
    sys.exit(0)

if __name__ == "__main__":
    stop_event = threading.Event()
    udp_thread = threading.Thread(target=start_udp_server, args=(stop_event,))
    udp_thread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        shutdown_server()
