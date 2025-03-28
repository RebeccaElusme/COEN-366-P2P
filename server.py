import socket
import json
import threading
import sys
import re
import time

# Server Configuration
SERVER_IP = "127.0.0.1"  # Server IP (localhost for testing)
SERVER_UDP_PORT = 5000  # UDP Port
SERVER_TCP_PORT = 6000  # TCP Port for purchase finalization

subscriptions = {}  # Key: item_name, Value: list of (buyer_name, buyer_address)
auction_items = {}  # Key: item_id or name, Value: item info
registered_clients = {} # Store registered users
lock = threading.Lock()

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

def get_registered_clients():
    """Returns the list of registered clients with full details."""
    with lock:
        if not registered_clients:
            return {"type": "CLIENT-LIST", "clients": []}
        return {"type": "CLIENT-LIST", "clients": list(registered_clients.values())}

def process_list_item(data, client_address):
    """Handles LIST_ITEM request from sellers."""
    item_name = data.get("item_name", "").strip()
    description = data.get("item_description", "").strip()
    start_price = data.get("start_price")
    duration = data.get("duration")
    rq_number = data.get("rq#", 0)

    if not item_name or not description or start_price is None or duration is None:
        return {"type": "LIST-DENIED", "rq#": rq_number, "reason": "Missing or invalid item fields."}

    # Validate types
    try:
        start_price = float(start_price)
        duration = int(duration)
    except ValueError:
        return {"type": "LIST-DENIED", "rq#": rq_number, "reason": "Price must be float and duration must be int."}

    with lock:
        if item_name in auction_items:
            return {"type": "LIST-DENIED", "rq#": rq_number, "reason": "Item name already listed."}

        # Store item in auction list
        auction_items[item_name] = {
            "item_name": item_name,
            "description": description,
            "start_price": start_price,
            "current_price": start_price,
            "seller_address": client_address,
            "highest_bidder": None,
            "duration": duration,
            "time_left": duration,
            "bids": [],
            "rq#": rq_number
        }

    return {"type": "ITEM_LISTED", "rq#": rq_number}
def process_subscription(data, client_address):
    """Handles SUBSCRIBE requests from buyers."""
    item_name = data.get("item_name", "").strip()
    rq_number = data.get("rq#", 0)

    if not item_name:
        return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Item name required"}

    # Check if user is registered and is a buyer
    buyer_name = None
    with lock:
        for name, info in registered_clients.items():
            if info["ip"] == client_address[0] and info["udp_port"] == client_address[1] and info["role"] == "Buyer":
                buyer_name = name
                break

        if not buyer_name:
            return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "You must be a registered buyer"}

        # Add to subscriptions
        if item_name not in subscriptions:
            subscriptions[item_name] = []

        # Prevent duplicate subscriptions
        if any(sub[0] == buyer_name for sub in subscriptions[item_name]):
            return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Already subscribed to this item"}

        subscriptions[item_name].append((buyer_name, client_address))

    return {"type": "SUBSCRIBED", "rq#": rq_number}
def process_unsubscribe(data, client_address):
    """Handles DE-SUBSCRIBE requests from buyers."""
    item_name = data.get("item_name", "").strip()
    rq_number = data.get("rq#", 0)

    if not item_name:
        return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Item name required"}

    with lock:
        if item_name not in subscriptions:
            return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Not subscribed"}

        # Identify buyer
        for i, (buyer_name, addr) in enumerate(subscriptions[item_name]):
            if addr == client_address:
                subscriptions[item_name].pop(i)
                return {"type": "DE-SUBSCRIBED", "rq#": rq_number}

    return {"type": "SUBSCRIPTION-DENIED", "rq#": rq_number, "reason": "Not subscribed to this item"}

def auction_announcement_loop(stop_event, server_socket):
    """Sends AUCTION_ANNOUNCE messages periodically to subscribed buyers."""
    while not stop_event.is_set():
        with lock:
            for item_name, item in list(auction_items.items()):
                item["time_left"] -= 5  # Decrease time

                if item["time_left"] <= 0:
                    continue  # Will be cleaned up in auction closure phase

                # Notify all subscribed buyers
                if item_name in subscriptions:
                    for buyer_name, buyer_address in subscriptions[item_name]:
                        announce_msg = {
                            "type": "AUCTION_ANNOUNCE",
                            "rq#": item["rq#"],  # Match to original listing
                            "item_name": item["item_name"],
                            "description": item["description"],
                            "current_price": item["current_price"],
                            "time_left": item["time_left"]
                        }
                        server_socket.sendto(json.dumps(announce_msg).encode(), buyer_address)
        time.sleep(5)

def process_bid(data, client_address):
    """Handles bid submissions and broadcasts bid updates."""
    item_name = data.get("item_name", "").strip()
    bid_amount = data.get("bid_amount")
    rq_number = data.get("rq#", 0)

    if not item_name or bid_amount is None:
        return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "Missing item name or bid amount."}

    try:
        bid_amount = float(bid_amount)
    except ValueError:
        return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "Bid must be a number."}

    with lock:
        if item_name not in auction_items:
            return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "Item not found or auction expired."}

        item = auction_items[item_name]

        # Identify bidder
        bidder_name = None
        for name, info in registered_clients.items():
            if info["ip"] == client_address[0] and info["udp_port"] == client_address[1] and info["role"] == "Buyer":
                bidder_name = name
                break

        if not bidder_name:
            return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "You must be a registered buyer."}

        if bid_amount <= item["current_price"]:
            return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "Bid too low."}

        # Accept the bid
        item["current_price"] = bid_amount
        item["highest_bidder"] = bidder_name
        item["bids"].append((bidder_name, bid_amount))

        # Notify all relevant clients
        update_msg = {
            "type": "BID_UPDATE",
            "rq#": item["rq#"],
            "item_name": item_name,
            "highest_bid": bid_amount,
            "bidder_name": bidder_name,
            "time_left": item["time_left"]
        }

        # Send to all subscribed buyers
        if item_name in subscriptions:
            for buyer_name, buyer_addr in subscriptions[item_name]:
                server_udp.sendto(json.dumps(update_msg).encode(), buyer_addr)

        # Send to seller
        seller_addr = item["seller_address"]
        server_udp.sendto(json.dumps(update_msg).encode(), seller_addr)

        return {"type": "BID_ACCEPTED", "rq#": rq_number}



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
            response = process_list_item(data, client_address)
        elif data["type"] == "SUBSCRIBE":
            response = process_subscription(data, client_address)
        elif data["type"] == "BID":
            response = process_bid(data, client_address)
        elif data["type"] == "DE-SUBSCRIBE":
            response = process_unsubscribe(data, client_address)
        else:
            response = {"type": "ERROR", "rq#": data.get("rq#", 0), "reason": "Invalid request"}
        server_socket.sendto(json.dumps(response).encode(), client_address)
    except (json.JSONDecodeError, ConnectionResetError):
        print(f"Error handling request from {client_address}")


def start_udp_server(stop_event):
    print(f"UDP Server listening on {SERVER_IP}:{SERVER_UDP_PORT}...")

    try:
        while not stop_event.is_set():
            server_udp.settimeout(1)
            try:
                message, client_address = server_udp.recvfrom(1024)
                threading.Thread(target=handle_client, args=(message, client_address, server_udp)).start()
            except socket.timeout:
                continue
    finally:
        server_udp.close()


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

server_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_udp.bind((SERVER_IP, SERVER_UDP_PORT))  # Replaces socket inside start_udp_server

# Run server
if __name__ == "__main__":
    stop_event = threading.Event()

    udp_thread = threading.Thread(target=start_udp_server, args=(stop_event,))
    tcp_thread = threading.Thread(target=start_tcp_server, args=(stop_event,))
    announce_thread = threading.Thread(target=auction_announcement_loop, args=(stop_event, socket.socket(socket.AF_INET, socket.SOCK_DGRAM)))

    udp_thread.start()
    tcp_thread.start()
    announce_thread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\nShutting down server")
        stop_event.set()
        udp_thread.join()
        tcp_thread.join()
        announce_thread.join()
        sys.exit(0)

    
