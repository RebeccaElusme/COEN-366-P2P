import socket
import json
import threading
import sys
import re
import random

# Server Configuration
SERVER_IP = "127.0.0.1"  # Server IP (localhost for testing)
SERVER_UDP_PORT = 5000  # UDP Port
SERVER_TCP_PORT = 6000  # TCP Port for purchase finalization

# Store registered users
registered_clients = {}
lock = threading.Lock()

#Store listings 
items_auctions = {}

#Subscriptions for the announcements 
subscriptions = {}

def process_registration(data, client_address):
    """Handles the REGISTER request with validation."""
    name = data["name"].strip()
    role = data["role"].strip().capitalize()
    udp_port = data["udp_port"]
    tcp_port = data["tcp_port"]
    rq_number = data.get("rq#", 0)

    # Validate name: must not be empty and cannot contain numbers or symbols
    if not name:
        return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Fields empty"}
    if not re.match(r"^[A-Za-z]+$", name):
        return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Invalid name format. Only letters allowed"}

    # Validate role: must be either "Buyer" or "Seller"
    if role not in ["Buyer", "Seller"]:
        return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Invalid role. Must be Buyer or Seller"}

    with lock:
        if name in registered_clients:
            return {"type": "REGISTER-DENIED", "rq#": rq_number, "reason": "Name already in use"}
        else:
            registered_clients[name] = {
                "name": name,
                "role": role,
                "ip": client_address[0],
                "udp_port": udp_port,
                "tcp_port": tcp_port,
                "rq#": rq_number
            }
            return {"type": "REGISTERED", "rq#": rq_number}

def process_deregistration(data):
    """Handles the DE-REGISTER request."""
    name = data["name"]
    rq_number = data.get("rq#", 0)
    
    with lock:
        if name in registered_clients:
            del registered_clients[name]
            response = {"type": "DE-REGISTERED", "rq#": rq_number}
        else:
            response = {"type": "DE-REGISTER-FAILED", "rq#": rq_number, "reason": "User not registered"}
    
    return response

def process_subscription(data, client_address):
    item_name = data.get("item_name")
    rq_number = data.get("rq#")

    with lock:
        if item_name not in items_auctions:
            return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Item not found"}

        if item_name not in subscriptions:
            subscriptions[item_name] = []

        # Avoid duplicates
        if client_address not in subscriptions[item_name]:
            subscriptions[item_name].append(client_address)

    return {"type": "SUBSCRIBED", "rq#": rq_number}


def get_registered_clients():
    """Returns the list of registered clients with full details."""
    with lock:
        if not registered_clients:
            return {"type": "CLIENT-LIST", "clients": []}
        return {"type": "CLIENT-LIST", "clients": list(registered_clients.values())}

def handle_client(message, client_address, server_socket):
    """Handles client messages in a separate thread."""
    try:
        data = json.loads(message.decode())
        print(f"Received message from {client_address}: {data}")

        if data["type"] == "REGISTER":
            response = process_registration(data, client_address)
        elif data["type"] == "DE-REGISTER":
            response = process_deregistration(data)
        elif data["type"] == "SHOW-CLIENTS":
            response = get_registered_clients()
        elif data["type"] == "LIST_ITEM":
            response = list_item(data, server_socket)
        elif data["type"] == "SUBSCRIBE":
            response = process_subscription(data, client_address)
        else:
            response = {"type": "ERROR", "rq#": data.get("rq#", 0), "reason": "Invalid request"}

        server_socket.sendto(json.dumps(response).encode(), client_address)
    except (json.JSONDecodeError, ConnectionResetError):
        print(f"Error handling request from {client_address}")

def start_udp_server(stop_event):
    """Starts the UDP server with multithreading support."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP, SERVER_UDP_PORT))
    print(f"UDP Server listening on {SERVER_IP}:{SERVER_UDP_PORT}...")
    
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

def start_tcp_server(stop_event):
    """Starts the TCP server for purchase finalization."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((SERVER_IP, SERVER_TCP_PORT))
    server_socket.listen(5)
    print(f"TCP Server listening on {SERVER_IP}:{SERVER_TCP_PORT}...")
    
    try:
        while not stop_event.is_set():
            server_socket.settimeout(1)
            try:
                client_socket, client_address = server_socket.accept()
                client_socket.close()
            except socket.timeout:
                continue
    finally:
        server_socket.close()

# List items for request from sellers
def list_item(data, server_socket):
    rq_number = data.get("rq#")
    item_name = data.get("item_name")
    item_description = data.get("item_description")
    start_price = data.get("start_price")
    duration = data.get("duration")


    if not all([item_name, item_description, isinstance(start_price, (int, float)), isinstance(duration, int)]):
        return {"type": "LIST-DENIED", "rq#": rq_number, "reason": "Invalid fields, please review your listing."}
    
    with lock:
        if item_name in items_auctions:
            return {"type": "LIST-DENIED", "rq#": rq_number, "reason": "Item already listed"}
    
       # If everything is correct, store the item
        items_auctions[item_name] = {
            "description": item_description,
            "start_price": start_price,
            "duration": duration,
            "current_price": start_price,
            "start_time": threading.Timer(duration, lambda: None)
        }

        print(f"Item '{item_name}' listed for auction. Notifying subscribers...")

        # For announcements
        if item_name in subscriptions:
            message = {
                "type": "AUCTION_ANNOUNCE",
                "rq#": random.randint(1000, 9999),  # can be any server-generated number
                "item_name": item_name,
                "description": item_description,
                "current_price": start_price,
                "time_left": duration
            }

            msg_encoded = json.dumps(message).encode()

            for subscriber_address in subscriptions[item_name]:
                try:
                    server_socket.sendto(msg_encoded, subscriber_address)
                    print(f"Sent AUCTION_ANNOUNCE to {subscriber_address}")
                except Exception as e:
                    print(f"Failed to send AUCTION_ANNOUNCE to {subscriber_address}: {e}")


        return {"type": "ITEM_LISTED", "rq#": rq_number}


# Run server
if __name__ == "__main__":
    stop_event = threading.Event()
    udp_thread = threading.Thread(target=start_udp_server, args=(stop_event,))
    tcp_thread = threading.Thread(target=start_tcp_server, args=(stop_event,))
    udp_thread.start()
    tcp_thread.start()
    
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down server")
        stop_event.set()
        udp_thread.join()
        tcp_thread.join()
        sys.exit(0)
