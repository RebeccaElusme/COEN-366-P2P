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

        # TCP Socket setup
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))  # Bind to any available TCP port
        self.tcp_port = self.tcp_socket.getsockname()[1]  # Get the assigned TCP port
        self.tcp_socket.listen(5)  # Listen for incoming connections

        self.server_address = ("127.0.0.1", 5000)  # Change to actual server IP if needed

        self.running = True  # To control thread shutdown
        threading.Thread(target=self.listen_for_messages, daemon=True).start()
        threading.Thread(target=self.listen_for_tcp_connections, daemon=True).start()


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
                
    def listen_for_tcp_connections(self):
        """Listen for TCP connections from the server."""
        while self.running:
            try:
                self.tcp_socket.settimeout(1)  # Non-blocking wait
                client_socket, addr = self.tcp_socket.accept()
                threading.Thread(target=self.handle_tcp_connection, args=(client_socket,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error accepting TCP connection: {e}")
                
    def handle_tcp_connection(self, client_socket):
        """Handle incoming TCP connection and messages."""
        try:
            data = client_socket.recv(1024)
            if data:
                response_data = json.loads(data.decode())
                self.handle_auction_closure_message(response_data)
        except Exception as e:
            print(f"Error handling TCP connection: {e}")
        finally:
            client_socket.close()
            
    def handle_auction_closure_message(self, response_data):
        """Handle auction closure messages from the server."""
        msg_type = response_data.get("type", "UNKNOWN")
        rqt = response_data.get("rq#", "Unknown")
        item_name = response_data.get("item_name", "Unknown")
        
        if msg_type == "WINNER":
            final_price = response_data.get('final_price', 0)
            seller_name = response_data.get('seller_name', 'Unknown')
            print(f"\nWINNER | {rqt} | {item_name} | {final_price} | {seller_name}")
            print("You won the auction for this item.")
            print("Please arrange payment and shipping with the seller.")
        
        elif msg_type == "SOLD":
            final_price = response_data.get('final_price', 0)
            buyer_name = response_data.get('buyer_name', 'Unknown')
            print(f"\nSOLD | {rqt} | {item_name} | {final_price} | {buyer_name}")
            print("Your item has been sold.")
            print("Please arrange payment and shipping with the buyer.")
        
        elif msg_type == "NON_OFFER":
            print(f"\nNON_OFFER | {rqt} | {item_name}")
            print("Your auction has ended with no bids.")
            print("You may want to list it again with a lower starting price.")
        
        elif msg_type == "LOSER":
            winner_price = response_data.get('winner_final_price', 0)
            winner_name = response_data.get('winner_name', 'Unknown')
            print(f"\nLOSER | {rqt} | {item_name} | {winner_price} | {winner_name}")
            print("You did not win this auction.")
        
        else:
            print(f"Unknown auction closure message: {response_data}")


## To close client socket
    def close_socket(self):
        self.running = False
        try:
            self.udp_socket.close()
            self.tcp_socket.close()
        except:
            pass  # Ignore errors during shutdown


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

        item_name = input("Enter the item name to subscribe to: ")
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

        print("\n[NEGOTIATION REQUEST]")
        print(f"Item: {item_name}")
        print(f"Current Price: {current_price}")
        print(f"Time Left: {time_left}s")
        print(f"RQ#: {rq_number}")

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


##########################################################################

#################### To handle responses from server #################
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
                    print("\n[NEGOTIATION REQUEST]")
                    print(f"Item: {response_data.get('item_name')}")
                    print(f"Current Price: {response_data.get('current_price')}")
                    print(f"Time Left: {response_data.get('time_left')}s")
                    print(f"RQ#: {rqt}")
                    self.handle_negotiate_request(response_data)
                else:
                    print("Unknown response:", response_data)

##############################################################
 # Run client
if __name__ == "__main__":
    try:
        client = AuctionClient()
        
        while True:
            time.sleep(0.5)
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

            else:
                print("Invalid option, please try again.")
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
        client.close_socket()
        sys.exit(0)