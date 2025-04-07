import threading
import socket
import json
import re
import sys
import time


class AuctionClient:
    #Class initialization
    def __init__(self):
        
        self.name = input("Enter name: ").strip().lower()
        while not self.name.isalpha():
                print("Invalid name. Try again.")
                self.name = input("Enter name: ").strip()


        self.role = self.get_valid_role()
        self.rq_counter = 0

        # Dynamically assign UDP and TCP ports
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))  # Bind to any available UDP port
        self.udp_port = self.udp_socket.getsockname()[1]  # Get the assigned UDP port

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))  # Bind to any available TCP port
        self.tcp_port = self.tcp_socket.getsockname()[1]  # Get the assigned TCP port

        self.server_address = ("127.0.0.1", 5000)  # Change to actual server IP if needed

        self.running = True  # To control thread shutdown

        # Controls meny display fir negotation 
        self.awaiting_negotiation_input = False  
        self.awaiting_finalization_input = False

        threading.Thread(target=self.listen_for_messages, daemon=True).start()

        # Start TCP listener thread
        threading.Thread(target=self.listen_for_tcp_messages, daemon=True).start()

    

    def get_valid_role(self):
        ## Prompt the user for  (Buyer/Seller).
        while True:
            role = input("Enter your role (Buyer/Seller): ").strip().capitalize()
            if role not in ["Buyer", "Seller"]:
                print("Invalid role. Please enter 'Buyer' or 'Seller'.")
            else:
                return role

    def send_register_request(self):
        ## Register request to server
        self.rq_counter += 1
        request = {
            "type": "REGISTER",
            "rq#": self.rq_counter,
            "name": self.name,
            "role": self.role,
            "ip": socket.gethostbyname(socket.gethostname()),  # Get local IP
            "udp_port": self.udp_port,
            "tcp_port": self.tcp_port
        }
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print(f"Sent REGISTER request: {request}")

    def send_deregister_request(self):
        ## DE-REGISTER request to server
        self.rq_counter += 1
        request = {
            "type": "DE-REGISTER",
            "rq#":self.rq_counter ,
            "name": self.name
        }
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print("Sent DE-REGISTER request:", request)

    def request_client_list(self):
        """Sends a request to the server to get the list of registered clients."""
        request = {"type": "SHOW-CLIENTS"}
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print("Requested list of registered clients...")


## Background thread for any UDP messages from the server
    def listen_for_messages(self):
        while self.running:
            try:
                self.udp_socket.settimeout(1)  # Non-blocking wait
                response, _ = self.udp_socket.recvfrom(1024)
                response_data = json.loads(response.decode())
                self.handle_server_response(response_data)
            except socket.timeout:
                continue  # just keep waiting
            except (json.JSONDecodeError, ConnectionResetError):
                print("Error receiving or decoding server message.")

## To close clinet socket
    def close_socket(self):
            self.running = False
            self.udp_socket.close()
            self.tcp_socket.close()


    ############# THIS IS TO PUT A LISTING UP ######################

    def send_list_item(self):
        if self.role != "Seller":
            print("Only sellers can list items.")
            return

        print("\n--- List an Item ---")
        item_name = input("Enter item name (or type 'cancel' to go back): ")
        if item_name == "cancel":
            print("Listing canceled")
            return

        item_description = input("Enter item description: ")

        while True:
            try:
                start_price_input = input("Enter starting price: ")
                duration_input = input("Enter auction duration (in seconds): ")

                start_price = float(start_price_input)
                duration = int(duration_input)

                # Request sent if input valid
                self.rq_counter += 1
                request = {
                    "type": "LIST_ITEM",
                    "rq#": self.rq_counter,
                    "name": self.name,  # <-- Add this line
                    "item_name": item_name,
                    "item_description": item_description,
                    "start_price": start_price,
                    "duration": duration
                }


                message = json.dumps(request).encode()
                self.udp_socket.sendto(message, self.server_address)
                print(f"Sent LIST_ITEM request: {request}")
                return  

            except ValueError:
                print(" Invalid price or duration.")
                retry = input("Try again? (yes/no): ")
                if retry != "yes":
                    print("Listing canceled.")
                    return
                else:
                    continue  

    ################################################################


#################### SUBSCRIBE TO ANNOUNCMENTS##########
    def send_subscribe_request(self):
        if self.role != "Buyer":
            print("Only buyers can subscribe to items.")
            return

        item_name = input("Enter the item name to subscribe to: ").strip().lower()
        if not item_name:
            print("Item name cannot be empty.")
            return

        self.rq_counter += 1
        request = {
            "type": "SUBSCRIBE",
            "rq#": self.rq_counter,
            "item_name": item_name
        }

        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print("Sent SUBSCRIBE request:", request)


    #########################################################

#################### UNSUBSCRIBE FROM ANNOUNCEMENTS ##########
    def send_unsubscribe_request(self):
            if self.role != "Buyer":
                print("Only buyers can unsubscribe from items.")
                return

            item_name = input("Enter the item name to unsubscribe from: ").strip()
            if not item_name:
                print("Item name cannot be empty.")
                return

            self.rq_counter += 1
            request = {
                "type": "DE-SUBSCRIBE",
                "rq#": self.rq_counter,
                "item_name": item_name
            }

            self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
            print("Sent DE-SUBSCRIBE request:", request)

######################################################################
###################   SEND A BID REQUEST  #####################################
    def send_bid_request(self):
        if self.role != "Buyer":
            print("Only buyers can place bids")
            return

        print("\n--Place a Bid--")
        item_name = input("Enter item name you want to bid on: ").strip()
        if not item_name:
            print("Item name cannot be empty.")
            return

        try:
            bid_amount = float(input("Enter your bid amount: ").strip())
        except ValueError:
            print("Invalid bid amount.")
            return

        try:
            rq_input = input("Enter the RQ# from the AUCTION_ANNOUNCE: ").strip()
            rq_number = int(rq_input)
        except ValueError:
            print("Invalid RQ#.")
            return

        self.rq_counter += 1
        request = {
            "type": "BID",
            "rq#": rq_number,  # This links to the original AUCTION_ANNOUNCE
            "item_name": item_name,
            "bid_amount": bid_amount,
            "bidder_name": self.name
        }

        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        print("Sent BID request:", request)

######################################################################

################################### NEGOTATION REQUEST #################

    def handle_negotiate_request(self, response_data):
        item_name = response_data.get("item_name")
        current_price = response_data.get("current_price")
        time_left = response_data.get("time_left")
        rq_number = response_data.get("rq#")

        self.awaiting_negotiation_input = True  # Block menu
        # Show prompt clearly
        print("\n NEGOTIATION REQUIRED")
        print(f"Item: {item_name}")
        print(f"Current Price: {current_price}")
        print(f"Time Left: {time_left}s")
        print(f"RQ#: {rq_number}")
        print("You must respond to this negotiation request now.")

        if self.role == "Seller":

            decision = input("Do you want to lower the price? (yes/no): ").strip().lower()
            if decision == "yes":
                try:
                    new_price = float(input("Enter new price: ").strip())
                    response = {
                        "type": "ACCEPT",
                        "rq#": rq_number,
                        "item_name": item_name,
                        "new_price": new_price
                    }
                except ValueError:
                    print("Invalid price entered. Sending REFUSE.")
                    response = {
                        "type": "REFUSE",
                        "rq#": rq_number,
                        "item_name": item_name,
                        "response": "REJECT"
                    }
            else:
                response = {
                    "type": "REFUSE",
                    "rq#": rq_number,
                    "item_name": item_name,
                    "response": "REJECT"
                }

            self.udp_socket.sendto(json.dumps(response).encode(), self.server_address)
            self.awaiting_negotiation_input = False  # Unblock menu

######################### LISTENING FOR TCP 2.6 #########################
    def listen_for_tcp_messages(self):
        self.tcp_socket.listen(5)
        print(f"[TCP] Listening for server messages on TCP port {self.tcp_port}...")

        while self.running:
            try:
                self.tcp_socket.settimeout(1)
                conn, addr = self.tcp_socket.accept()
                with conn:
                    data = conn.recv(1024)
                    if not data:
                        continue

                    try:
                        message = json.loads(data.decode())
                        self.handle_tcp_message(message)
                    except json.JSONDecodeError:
                        print("[TCP] Received malformed JSSON from server.")
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[TCP] Error receiving TCP message: {e}")


##########################################################################

################################## Handle TCP messages from server

    def handle_tcp_message(self, message):
        msg_type = message.get("type")
        rq = message.get("rq#", "Unknown")

        if msg_type == "WINNER":
            print("\n[TCP]  YOU ARE THE WINNER ")
            print(f"Item: {message['item_name']}")
            print(f"Final Price: {message['final_price']}")
            print(f"Seller: {message['seller_name']}")
            print(f"RQ#: {rq}")

        elif msg_type == "SOLD":
            print("\n[TCP] Your item was SOLD.")
            print(f"Item: {message['item_name']}")
            print(f"Final Price: {message['final_price']}")
            print(f"Buyer: {message['buyer_name']}")
            print(f"RQ#: {rq}")

        elif msg_type == "NO_SALE":
            print("\n[TCP] Your auction ended with no bids.")
            print(f"Item: {message['item_name']}")
            print(f"RQ#: {rq}")
        elif msg_type == "INFORM_Req":
            item = message.get("item_name")
            price = message.get("final_price")
            print(f"\n[TCP] Finalizing Purchase for item '{item}' at price ${price}")
            self.respond_to_inform_req(message)
        elif msg_type == "CANCEL":
            print("\n[TCP] Transaction was CANCELLED.")
            print(f"Reason: {message.get('reason')}")
        elif msg_type == "Shipping_Info":
            buyer = message.get("name", "Unknown")
            address = message.get("winner_address", "N/A")
            price = float(message.get("final_price", 0))
            seller_earning = round(price * 0.9, 2)

            print("\n[TCP] Transaction completed successfully.")
            print(f"Buyer: {buyer}")
            print(f"Shipping Address: {address}")
            print(f"Final Price: ${price}")
            print(f"You will receive: ${seller_earning} after service fees.")
            print("Please proceed to ship the item via surface mail.")

        else:
            print("[TCP] Unknown message received:")
            print(message)

    def respond_to_inform_req(self, message):
        
        self.awaiting_finalization_input = True

        rq_number = message.get("rq#")
        item_name = message.get("item_name")

        response = {
            "type": "INFORM_Res",
            "rq#": rq_number,
            "name": self.name
        }

        if self.role == "Buyer":
            print("Please enter payment and shipping details.")

            cc = input("Credit Card Number (16 digits): ").strip()
            exp = input("Expiration Date (MM/YY): ").strip()
            address = input("Shipping Address: ").strip()

            response.update({
                "cc#": cc,
                "cc_exp_date": exp,
                "address": address
            })

        else:  # Seller
            print("Please enter your address for shipping receipt.")
            address = input("Your Address: ").strip()
            response["address"] = address

        # Send response back to server via TCP
        try:
            response_port = message.get("response_port", 6000)  # fallback to 6000 if not present
            with socket.create_connection(("127.0.0.1", response_port), timeout=5) as sock:

                sock.sendall(json.dumps(response).encode())
                print("Sent INFORM_Res back to server.")
        except Exception as e:
            print(f"Failed to send INFORM_Res: {e}")

        self.awaiting_finalization_input = False

#################### To handle UDP responses from server #################
    def handle_server_response(self, response_data):
                rqt = response_data.get("rq#", "Unknown")
                msg_type = response_data.get("type", "UNKNOWN")

                if msg_type == "REGISTERED":
                    print(f"Registered successfully (RQ# {rqt})")
                elif msg_type == "REGISTER-DENIED":
                    print(f"Registration failed (RQ# {rqt}): {response_data.get('reason', 'Unknown error')}")
                elif msg_type == "DE-REGISTERED":
                    print(f"De-registered successfully (RQ# {rqt})")
                elif msg_type == "CLIENT-LIST":
                    print("\nRegistered Clients:")
                    for client in response_data.get("clients", []):
                        print(f"- {client.get('name')} ({client.get('role')})")
                elif msg_type == "ITEM_LISTED":
                    print(f"Item listed successfully (RQ# {rqt})")
                elif msg_type == "LIST-DENIED":
                    print("Item listing denied (RQ# {rqt}):", response_data.get('reason'))
                elif msg_type == "SUBSCRIBED":
                    print(f"Subscribed successfully (RQ# {rqt})")
                elif msg_type == "SUBSCRIPTION-DENIED":
                    print(f"Subscription failed (RQ# {rqt}): {response_data.get('reason')}")
                elif msg_type == "UNSUBSCRIBED":
                    print(f"Unsubscribed successfully (RQ# {rqt})")
                elif msg_type == "UNSUBSCRIBE-FAILED":
                    print(f"Unsubscribe failed (RQ# {rqt}): {response_data.get('reason')}")
                elif msg_type == "AUCTION_ANNOUNCE":
                    print("\n AUCTION ANNOUNCEMENT:")
                    print(f"Item: {response_data.get('item_name')}")
                    print(f"Description: {response_data.get('description')}")
                    print(f"Current Price: {response_data.get('current_price')}")
                    print(f"Time Left: {response_data.get('time_left')}s")
                    print(f"RQ#: {response_data.get('rq#')}")
                elif msg_type == "BID_UPDATE":
                    print("\nBID UPDATE:")
                    print(f"Item: {response_data.get('item_name')}")
                    print(f"Highest Bid: {response_data.get('highest_bid')}")
                    print(f"Bidder: {response_data.get('bidder_name')}")
                    print(f"Time Left: {response_data.get('time_left')}s")
                    print(f"RQ#: {rqt}")
                elif msg_type == "BID_ACCEPTED":
                    print(f"BID ACCEPTED (RQ# {rqt})")
                elif msg_type == "BID_REJECTED":
                    print(f"BID REJECTED (RQ# {rqt}): {response_data.get('reason')}")
                elif msg_type == "NEGOTIATE_REQ":
                    self.handle_negotiate_request(response_data)
                elif msg_type == "ACCEPT_CONFIRMED":
                    print(f"Server confirmed price adjustment (RQ# {rqt})")
                elif msg_type == "PRICE_ADJUSTMENT":
                    print("\nPRICE ADJUSTMENT:")
                    print(f"Item: {response_data.get('item_name')}")
                    print(f"New Price: {response_data.get('new_price')}")
                    print(f"Time Left: {response_data.get('time_left')}s")
                    print(f"RQ#: {rqt}")
                else:
                    print("Unknown response:", response_data)


##############################################################
 # Run client
if __name__ == "__main__":
    try:
        client = AuctionClient()
        
        while True:
            time.sleep(0.5)
            if client.awaiting_negotiation_input or client.awaiting_finalization_input:
                continue

            print("\nOptions:")
            print("1. Register")
            print("2. De-register")
            print("3. Show List of Clients")
            print("4. List Item (Sellers Only)")
            print("5. Subscribe to Item Announcement (Buyer)")
            print("6. Unsubscribe from Item (Buyer)")
            print("7. Place a Bid (Buyer)")
            print("8. Exit")

            choice = input("Enter your choice: ").strip()

            if choice == "1":
                client.send_register_request()
            elif choice == "2":
                client.send_deregister_request()
            elif choice == "3":
                client.request_client_list()
            elif choice == "4":
                client.send_list_item()
            elif choice == "5":
                client.send_subscribe_request()
            elif choice == "6":
                client.send_unsubscribe_request()
            elif choice == "7":
                client.send_bid_request()
            elif choice == "8":
                print("Exiting client...")
                client.close_socket()
                sys.exit(0)
            elif choice == "9":
                 client.send_tcp_test()
            else:
                print("Invalid option, please try again.")
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
        client.close_socket()
        sys.exit(0)
