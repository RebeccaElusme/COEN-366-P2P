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
    item_name = data.get("item_name").strip().lower()
    rq_number = data.get("rq#")

    with lock:
        if item_name not in subscriptions:
            subscriptions[item_name] = []

        for addr in subscriptions[item_name]:
            if addr == client_address:
                return {"type": "SUBSCRIBED", "rq#": rq_number}  # Already subscribed

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
    item_name = data.get("item_name").strip().lower()
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
                print(f"[TCP] Connection from {client_address}")
                
                # Add this to receive and print the message
                data = client_socket.recv(1024)
                print(f"[TCP] Received: {data.decode()}")

                client_socket.close()
            except socket.timeout:
                continue
    finally:
        server_socket.close()


# List items for request from sellers
def list_item(data, server_socket):
    rq_number = data.get("rq#")
    item_name = data.get("item_name").strip().lower()
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
    item_name = data.get("item_name").strip().lower()
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
        return None  # No need to send further response here

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


################################################################

############ To control the durstion ahd thread time ##########
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
                            if isinstance(server_socket, socket.socket):
                                try:
                                    server_socket.sendto(json.dumps(negotiate_req).encode(), seller_addr)
                                    print(f"Sent NEGOTIATE_REQ to seller {seller_name}")
                                except Exception as e:
                                    print(f"[ERROR] Failed to send NEGOTIATE_REQ: {e}")
                            else:
                                print("[ERROR] server_socket is not a valid socket object.")

                            print(f"Sent NEGOTIATE_REQ to seller {seller_name}")
                    else:
                        print(f"[DEBUG] Skipping NEGOTIATE_REQ for {item_name}: sent={auction.get('negotiation_sent')}, bidder={auction.get('highest_bidder')}, time_left={time_left}")

    # When the auction ends 
    print(f"Auction for '{item_name}' (RQ# {rq_number}) ended.")

    auction_list = items_auctions.get(item_name, [])
    for auction in auction_list:
        if auction["announcement_rq"] != rq_number:
            continue

        if "highest_bidder" in auction:
            buyer_name = auction["highest_bidder"]
            seller_name = auction["seller"]
            final_price = auction["current_price"]

            buyer_info = registered_clients.get(buyer_name.lower())
            seller_info = registered_clients.get(seller_name.lower())

            if buyer_info:
                try:
                    with socket.create_connection((buyer_info["ip"], buyer_info["tcp_port"]), timeout=5) as sock:
                        winner_msg = {
                            "type": "WINNER",
                            "rq#": rq_number,
                            "item_name": item_name,
                            "final_price": final_price,
                            "seller_name": seller_info["name"]
                        }
                        sock.sendall(json.dumps(winner_msg).encode())
                        print(f"[TCP] Sent WINNER to {buyer_name}")
                except Exception as e:
                    print(f"[TCP] Failed to send WINNER to {buyer_name}: {e}")

            if seller_info:
                try:
                    with socket.create_connection((seller_info["ip"], seller_info["tcp_port"]), timeout=5) as sock:
                        sold_msg = {
                            "type": "SOLD",
                            "rq#": rq_number,
                            "item_name": item_name,
                            "final_price": final_price,
                            "buyer_name": buyer_info["name"]
                        }
                        sock.sendall(json.dumps(sold_msg).encode())
                        print(f"[TCP] Sent SOLD to {seller_name}")
                except Exception as e:
                    print(f"[TCP] Failed to send SOLD to {seller_name}: {e}")
            finalize_purchase(item_name, rq_number, buyer_name, seller_name, final_price)
        else:
            # No one bid — notify seller
            seller_name = auction["seller"]
            seller_info = registered_clients.get(seller_name.lower())

            if seller_info:
                try:
                    with socket.create_connection((seller_info["ip"], seller_info["tcp_port"]), timeout=5) as sock:
                        no_sale_msg = {
                            "type": "NO_SALE",
                            "rq#": rq_number,
                            "item_name": item_name
                        }
                        sock.sendall(json.dumps(no_sale_msg).encode())
                        print(f"[TCP] Sent NO_SALE to {seller_name}")
                except Exception as e:
                    print(f"[TCP] Failed to send NO_SALE to {seller_name}: {e}")



def finalize_purchase(item_name, rq_number, buyer_name, seller_name, final_price):
    import time

    buyer = registered_clients.get(buyer_name.lower())
    seller = registered_clients.get(seller_name.lower())

    if not buyer or not seller:
        print(f"[TCP] Missing buyer/seller info for finalization.")
        return

    tcp_receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_receiver.bind((SERVER_IP, 0))  # bind to any free port
    receiver_port = tcp_receiver.getsockname()[1]  # get assigned port
    tcp_receiver.listen(2)
    tcp_receiver.settimeout(120)
    
    # Step 1: Send INFORM_Req to both
    inform_msg = {
        "type": "INFORM_Req",
        "rq#": rq_number,
        "item_name": item_name,
        "final_price": final_price,
        "response_port": receiver_port  # tell client where to send INFORM_Res
    }   


    for user in [buyer, seller]:
        try:
            with socket.create_connection((user["ip"], user["tcp_port"]), timeout=5) as sock:
                sock.sendall(json.dumps(inform_msg).encode())
        except Exception as e:
            print(f"[TCP] Could not send INFORM_Req to {user['name']}: {e}")
            return  # Fail early

    # Step 2: Listen for INFORM_Res responses
    responses = {}



    print(f"[TCP] Waiting for INFORM_Res from buyer and seller...")

    start = time.time()
    while len(responses) < 2 and time.time() - start < 120:
        try:
            conn, _ = tcp_receiver.accept()
            data = conn.recv(1024)
            msg = json.loads(data.decode())
            name = msg.get("name", "").strip().lower()
            responses[name] = msg
            print(f"[TCP] Received INFORM_Res from {name}")
        except socket.timeout:
            break
        except Exception as e:
            print(f"[TCP] Error while waiting for INFORM_Res: {e}")
    tcp_receiver.close()

    # Step 3: Check both responses exist
    print("[DEBUG] Buyer expected:", buyer_name.lower())
    print("[DEBUG] Seller expected:", seller_name.lower())
    print("[DEBUG] Received responses from:", list(responses.keys()))

    if buyer_name.lower() not in responses or seller_name.lower() not in responses:
        reason = "Did not receive all required payment details"
        cancel_msg = {
            "type": "CANCEL",
            "rq#": rq_number,
            "reason": reason
        }
        for user in [buyer, seller]:
            try:
                with socket.create_connection((user["ip"], user["tcp_port"]), timeout=5) as sock:
                    sock.sendall(json.dumps(cancel_msg).encode())
            except:
                pass
        print("[TCP] Finalization cancelled: one party did not respond")
        return

    buyer_data = responses[buyer_name.lower()]
    seller_data = responses[seller_name.lower()]

    # Step 4: Validate buyer's credit card + address
    if not re.match(r"^\d{16}$", buyer_data.get("cc#", "")):
        reason = "Invalid credit card format"
    elif not re.match(r"^(0[1-9]|1[0-2])/\d{2}$", buyer_data.get("cc_exp_date", "")):
        reason = "Invalid expiration date format"
    elif not buyer_data.get("address"):
        reason = "Missing shipping address"
    elif random.random() < 0.05:
        reason = "Bank rejected the payment"
    else:
        reason = None

    if reason:
        cancel_msg = {
            "type": "CANCEL",
            "rq#": rq_number,
            "reason": reason
        }
        for user in [buyer, seller]:
            try:
                with socket.create_connection((user["ip"], user["tcp_port"]), timeout=5) as sock:
                    sock.sendall(json.dumps(cancel_msg).encode())
            except:
                pass
        print(f"[TCP] Finalization failed: {reason}")
        return

    # Step 5: Success → send Shipping_Info to seller
    shipping_info = {
        "type": "Shipping_Info",
        "rq#": rq_number,
        "name": buyer_name,
        "winner_address": buyer_data["address"]
    }

    try:
        with socket.create_connection((seller["ip"], seller["tcp_port"]), timeout=5) as sock:
            sock.sendall(json.dumps(shipping_info).encode())
            print("[TCP] Shipping_Info sent to seller.")
    except Exception as e:
        print(f"[TCP] Could not send Shipping_Info: {e}")


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
