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

def process_registration(data, client_address, server_socket):
    """Handles the REGISTER request with validation."""
    name = data["name"].strip().lower()
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

def process_subscription(data, client_address,server_socket):
    item_name = data.get("item_name")
    rq_number = data.get("rq#")

    with lock:
        if item_name not in subscriptions:
            subscriptions[item_name] = []

        if client_address not in subscriptions[item_name]:
            subscriptions[item_name].append(client_address)

        #  Send announcement now if item already here
        if item_name in items_auctions:
            for auction in items_auctions[item_name]:
                auction_announce = {
                    "type": "AUCTION_ANNOUNCE",
                    "rq#": auction["announcement_rq"],
                    "item_name": item_name,
                    "description": auction["description"],
                    "current_price": auction["current_price"],
                    "time_left": auction["duration"]
                }
                server_socket.sendto(json.dumps(auction_announce).encode(), client_address)
                print(f"Sent AUCTION_ANNOUNCE (existing) to {client_address}")

    return {"type": "SUBSCRIBED", "rq#": rq_number}

def process_unsubscribe(data, client_address):
    item_name = data.get("item_name")
    rq_number = data.get("rq#")

    with lock:
        if item_name not in subscriptions:
            return {"type": "UNSUBSCRIBE-FAILED", "rq#": rq_number, "reason": "Item not found"}

        if client_address not in subscriptions[item_name]:
            return {"type": "UNSUBSCRIBE-FAILED", "rq#": rq_number, "reason": "You are not subscribed to this item"}

        subscriptions[item_name].remove(client_address)
        return {"type": "UNSUBSCRIBED", "rq#": rq_number}


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
            response = process_registration(data, client_address,server_socket)
        elif data["type"] == "DE-REGISTER":
            response = process_deregistration(data)
        elif data["type"] == "SHOW-CLIENTS":
            response = get_registered_clients()
        elif data["type"] == "LIST_ITEM":
            response = list_item(data, server_socket)
        elif data["type"] == "SUBSCRIBE":
            response = process_subscription(data, client_address,server_socket)
        elif data["type"] == "DE-SUBSCRIBE":
            response = process_unsubscribe(data, client_address)
        elif data["type"] == "BID":
            response = process_bid(data, client_address, server_socket)
            if response:
                server_socket.sendto(json.dumps(response).encode(), client_address)
            return  # Prevent sending 'None' below for this BID case
        elif data["type"] == "ACCEPT":
            response = process_accept(data, server_socket)
            if response:
                server_socket.sendto(json.dumps(response).encode(), client_address)
            return

        elif data["type"] == "REFUSE":
            print(f"Seller refused negotiation for item '{data.get('item_name')}' (RQ# {data.get('rq#')})")
            return


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

#Establish TCP connections to send messages
def tcp_send_message(client_name, message):
    """Establishes a TCP connection with a client and sends a message."""
    if client_name not in registered_clients:
        print(f"Client {client_name} not found.")
        return False

    client = registered_clients[client_name]
    client_ip = client["ip"]
    client_tcp_port = client["tcp_port"]

    try:
        # Create a TCP socket
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((client_ip, client_tcp_port))
        
        # Send the message
        client_socket.sendall(json.dumps(message).encode())
        client_socket.close()
        return True
    except Exception as e:
        print(f"Error sending TCP message to {client_name}: {e}")
        return False
    

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
        if item_name not in items_auctions:
            items_auctions[item_name] = []

        announcement_rq = random.randint(1000, 9999)

        new_auction = {
            "description": item_description,
            "start_price": start_price,
            "duration": duration,
            "current_price": start_price,
            "announcement_rq": announcement_rq,
            "seller": data.get("name").strip().lower()
        }

        items_auctions[item_name].append(new_auction)

        print(f"Item '{item_name}' listed by seller. Sending AUCTION_ANNOUNCE to subscribers...")

        if item_name in subscriptions:
            message = {
                "type": "AUCTION_ANNOUNCE",
                "rq#": announcement_rq,
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
                    print(f"Failed to send to {subscriber_address}: {e}")

    #### Lancement du thread 
    threading.Thread(
        target=auction_timer,
        args=(item_name, announcement_rq, duration, server_socket),
        daemon=True
    ).start()

    return {"type": "ITEM_LISTED", "rq#": rq_number}

###################### PROCESSE BID ############################

def process_bid(data, client_address, server_socket):
    rq_number = data.get("rq#")
    item_name = data.get("item_name")
    bid_amount = data.get("bid_amount")
    bidder_name = data.get("bidder_name")

    with lock:
        if item_name not in items_auctions:
            return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "No active auction for this item"}

        auction_list = items_auctions[item_name]

        # Try to find the auction matching the RQ#
        matching_auction = None
        for auction in auction_list:
            if auction["announcement_rq"] == rq_number:
                matching_auction = auction
                break

        if not matching_auction:
            return {"type": "BID_REJECTED", "rq#": rq_number, "reason": "Invalid RQ# for this item"}

        if not isinstance(bid_amount, (int, float)) or bid_amount <= matching_auction["current_price"]:
            return {
                "type": "BID_REJECTED",
                "rq#": rq_number,
                "reason": f"Bid must be higher than current price ({matching_auction['current_price']})"
            }
        
        if matching_auction["duration"] <= 0:
            return {
                "type": "BID_REJECTED",
                "rq#": rq_number,
                "reason": "Auction has ended, no more bids accepted !"
            }

        # Track all bidders for later notifications
        if "all_bidders" not in matching_auction:
            matching_auction["all_bidders"] = []
        if bidder_name not in matching_auction["all_bidders"]:
            matching_auction["all_bidders"].append(bidder_name)

        # Accept bid
        matching_auction["current_price"] = bid_amount
        matching_auction["highest_bidder"] = bidder_name

        # Send BID_ACCEPTED to bidder
        server_socket.sendto(json.dumps({"type": "BID_ACCEPTED", "rq#": rq_number}).encode(), client_address)

        # Prepare BID_UPDATE message
        bid_update = {
            "type": "BID_UPDATE",
            "rq#": rq_number,
            "item_name": item_name,
            "highest_bid": bid_amount,
            "bidder_name": bidder_name,
            "time_left": matching_auction["duration"]  # For now, not dynamically updated
        }

        msg_encoded = json.dumps(bid_update).encode()

        # Notify all subscribers
        if item_name in subscriptions:
            for sub_addr in subscriptions[item_name]:
                server_socket.sendto(msg_encoded, sub_addr)

        # Notify seller (we'll assume first seller who listed it)
        seller_name = matching_auction.get("seller")
        if seller_name and seller_name in registered_clients:
            seller = registered_clients[seller_name]
            seller_addr = (seller["ip"], seller["udp_port"])
            server_socket.sendto(msg_encoded, seller_addr)

        print(f"Accepted bid from {bidder_name} on '{item_name}' for {bid_amount}")
        return None  # No need to send further response here    return None  # No need to send further response here

###### Process Negotation ####
def process_accept(data, server_socket):
    rq_number = data.get("rq#")
    item_name = data.get("item_name")
    new_price = data.get("new_price")

    with lock:
        auction_list = items_auctions.get(item_name, [])
        for auction in auction_list:
            if auction["announcement_rq"] == rq_number:
                auction["current_price"] = new_price

                # Notify all subscribers
                adjustment = {
                    "type": "PRICE_ADJUSTMENT",
                    "rq#": rq_number,
                    "item_name": item_name,
                    "new_price": new_price,
                    "time_left": auction["duration"]
                }

                message = json.dumps(adjustment).encode()
                for sub in subscriptions.get(item_name, []):
                    server_socket.sendto(message, sub)

                print(f"Price adjusted for '{item_name}' to {new_price}, sent to all subscribers.")
                return {"type": "ACCEPT_CONFIRMED", "rq#": rq_number}


def auction_timer(item_name, rq_number, duration, server_socket):
    import time

    time_left = duration

    for _ in range(duration):
        time.sleep(1)
        time_left -= 1

        with lock:
            auction_list = items_auctions.get(item_name, [])
            for auction in auction_list:
                if auction["announcement_rq"] == rq_number:
                    auction["duration"] = time_left

                    if not auction.get("negotiation_sent") and time_left <= (duration // 2) and "highest_bidder" not in auction:
                        print(f"[DEBUG] Sending NEGOTIATE_REQ for {item_name} at time_left={time_left}")

                        auction["negotiation_sent"] = True
                        seller_name = auction.get("seller", "").strip().lower()
                        if seller_name and seller_name in registered_clients:
                            seller = registered_clients[seller_name]
                            seller_addr = (seller["ip"], seller["udp_port"])

                            negotiate_req = {
                                "type": "NEGOTIATE_REQ",
                                "rq#": rq_number,
                                "item_name": item_name,
                                "current_price": auction["current_price"],
                                "time_left": time_left
                            }
                            server_socket.sendto(json.dumps(negotiate_req).encode(), seller_addr)
                            print(f"Sent NEGOTIATE_REQ to seller {seller_name}")
                    else:
                        print(f"[DEBUG] Skipping NEGOTIATE_REQ for {item_name}: sent={auction.get('negotiation_sent')}, bidder={auction.get('highest_bidder')}, time_left={time_left}")

        if time_left == 0:
            print(f"Auction for '{item_name}' (RQ# {rq_number}) ended.")
            # Call auction_closure to notify winner and seller
            auction_closure(item_name, rq_number, server_socket)

######### AUNCTION CLOSURE: WINNER, LOSER, NO OFFER  #################################
def auction_closure(item_name, rq_number, server_socket):
    """Handles the closure of an auction, notifying the winner and the seller."""
    # Get the auction details
    with lock:
        auction_list = items_auctions.get(item_name, [])
        if not auction_list:
            print(f"No auction found for item {item_name}.")
            return
        
        # Find the auction for the specific RQ#
        auction_to_close = None
        for auction in auction_list:
            if auction["announcement_rq"] == rq_number:
                auction_to_close = auction
                break
        
        if not auction_to_close:
            print(f"No auction found for item {item_name} with RQ# {rq_number}.")
            return
        
        seller_name = auction_to_close.get("seller")
        highest_bidder = auction_to_close.get("highest_bidder")
        winning_bid = auction_to_close.get("current_price")
        
        # Track all bidders to notify losers
        all_bidders = auction_to_close.get("all_bidders", [])
        if highest_bidder and highest_bidder not in all_bidders:
            all_bidders.append(highest_bidder)
        
        # Remove the auction from the active auctions list
        items_auctions[item_name].remove(auction_to_close)
        if not items_auctions[item_name]:
            del items_auctions[item_name]

    # Case when no bids were placed
    if not highest_bidder:
        # Send NON_OFFER message to seller using TCP
        message = {
            "type": "NON_OFFER",
            "rq#": rq_number,
            "item_name": item_name
        }
        success = tcp_send_message(seller_name, message)
        if success:
            print(f"Sent NON_OFFER to seller {seller_name}.")
        return

    # Send WINNER message to the highest bidder (buyer) using TCP
    winner_message = {
        "type": "WINNER",
        "rq#": rq_number,
        "item_name": item_name,
        "final_price": winning_bid,
        "seller_name": seller_name
    }
    success = tcp_send_message(highest_bidder, winner_message)
    if success:
        print(f"Sent WINNER message to {highest_bidder}.")

    # Send SOLD message to the seller using TCP
    sold_message = {
        "type": "SOLD",
        "rq#": rq_number,
        "item_name": item_name,
        "final_price": winning_bid,
        "buyer_name": highest_bidder
    }
    success = tcp_send_message(seller_name, sold_message)
    if success:
        print(f"Sent SOLD message to seller {seller_name}.")
    
    # Notify all losing bidders
    for bidder in all_bidders:
        if bidder != highest_bidder:
            loser_message = {
                "type": "LOSER",
                "rq#": rq_number,
                "item_name": item_name,
                "winner_final_price": winning_bid,
                "winner_name": highest_bidder
            }
            tcp_send_message(bidder, loser_message)
            print(f"Sent LOSER notification to {bidder}.")

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
