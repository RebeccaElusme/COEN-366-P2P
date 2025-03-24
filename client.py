import threading
import socket
import json
import re
import sys


class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = self.get_valid_name()
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
        threading.Thread(target=self.listen_for_messages, daemon=True).start()

    def get_valid_name(self):
        """Prompt the user until they enter a valid name (letters only)."""
        while True:
            name = input("Enter your unique name: ").strip()
            if not name:
                print("Name cannot be empty. Please enter a valid name.")
            elif not re.match("^[A-Za-z]+$", name):
                print("Invalid name format. Only letters are allowed.")
            else:
                return name

    def get_valid_role(self):
        """Prompt the user until they enter a valid role (Buyer/Seller)."""
        while True:
            role = input("Enter your role (Buyer/Seller): ").strip().capitalize()
            if role not in ["Buyer", "Seller"]:
                print("Invalid role. Please enter 'Buyer' or 'Seller'.")
            else:
                return role

    def send_register_request(self):
        """Sends a REGISTER request to the server."""
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
        self.listen_for_response()

    def send_deregister_request(self):
        """Sends a DE-REGISTER request to the server."""
        self.rq_counter += 1
        request = {
            "type": "DE-REGISTER",
            "rq#":self.rq_counter ,
            "name": self.name
        }
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print(f"Sent DE-REGISTER request: {request}")
        self.listen_for_response()

    def request_client_list(self):
        """Sends a request to the server to get the list of registered clients."""
        request = {"type": "SHOW-CLIENTS"}
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print("Requested list of registered clients...")
        self.listen_for_response()


## Background thread for any UDP messages from the server
    def listen_for_messages(self):
        while self.running:
            try:
                self.udp_socket.settimeout(1)  # Non-blocking wait
                response, _ = self.udp_socket.recvfrom(1024)
                response_data = json.loads(response.decode())
                self.handle_server_response(response_data)
            except socket.timeout:
                continue  # Normal timeout — just keep waiting
            except (json.JSONDecodeError, ConnectionResetError):
                print("Error receiving or decoding server message.")

        def close_socket(self):
            ###Closes the client socket.
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
                    "item_name": item_name,
                    "item_description": item_description,
                    "start_price": start_price,
                    "duration": duration
                }

                message = json.dumps(request).encode()
                self.udp_socket.sendto(message, self.server_address)
                print(f"Sent LIST_ITEM request: {request}")
                self.listen_for_response()

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

# Run client
if __name__ == "__main__":
    try:
        client = AuctionClient()
        
        while True:
            print("\nOptions:\n1. Register\n2. De-register\n3. Show List of Clients\n4. List Item (Sellers Only)\n5. Exit")
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
                print("Exiting client...")
                client.close_socket()
                sys.exit(0)
            else:
                print("Invalid option, please try again.")
    except KeyboardInterrupt:
        print("\nClient terminated by user.")
        client.close_socket()
        sys.exit(0)
