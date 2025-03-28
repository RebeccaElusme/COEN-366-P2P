import socket
import json
import re
import sys

class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = self.get_valid_name()
        self.role = self.get_valid_role()

        # Dynamically assign UDP and TCP ports
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))  # Bind to any available UDP port
        self.udp_port = self.udp_socket.getsockname()[1]  # Get the assigned UDP port

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))  # Bind to any available TCP port
        self.tcp_port = self.tcp_socket.getsockname()[1]  # Get the assigned TCP port

        self.server_address = ("127.0.0.1", 5000)  # Change to actual server IP if needed

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

    def list_item(self):
        """Allows a seller to list an item for auction."""
        if self.role != "Seller":
            print("Only users with the 'Seller' role can list items.")
            return

        item_name = input("Enter item name: ").strip()
        item_description = input("Enter item description: ").strip()

        try:
            start_price = float(input("Enter starting price: "))
            duration = int(input("Enter auction duration (in seconds): "))
        except ValueError:
            print("Invalid input. Price must be a number and duration must be an integer.")
            return

        request = {
            "type": "LIST_ITEM",
            "rq#": 10,  # You can use a dynamic counter or uuid if you want
            "item_name": item_name,
            "item_description": item_description,
            "start_price": start_price,
            "duration": duration
        }

        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        print(f"Sent LIST_ITEM request: {request}")
        self.listen_for_response()

    def send_register_request(self):
        """Sends a REGISTER request to the server."""
        request = {
            "type": "REGISTER",
            "rq#": 1,
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
        request = {
            "type": "DE-REGISTER",
            "rq#": 2,
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

    def subscribe_to_item(self):
        if self.role != "Buyer":
            print("Only buyers can subscribe to auctions.")
            return

        item_name = input("Enter the item name to subscribe to: ").strip()
        if not item_name:
            print("Item name cannot be empty.")
            return

        request = {
            "type": "SUBSCRIBE",
            "rq#": 20,
            "item_name": item_name
        }

        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        self.listen_for_response()

    def unsubscribe_from_item(self):
        if self.role != "Buyer":
            print("Only buyers can unsubscribe from auctions.")
            return

        item_name = input("Enter the item name to unsubscribe from: ").strip()
        if not item_name:
            print("Item name cannot be empty.")
            return

        request = {
            "type": "DE-SUBSCRIBE",
            "rq#": 21,
            "item_name": item_name
        }

        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, self.server_address)
        self.listen_for_response()

    def place_bid(self):
        if self.role != "Buyer":
            print("Only buyers can place bids.")
            return

        item_name = input("Enter the item name you want to bid on: ").strip()
        try:
            bid_amount = float(input("Enter your bid amount: "))
        except ValueError:
            print("Invalid input. Bid must be a number.")
            return

        request = {
            "type": "BID",
            "rq#": 30,
            "item_name": item_name,
            "bid_amount": bid_amount
        }

        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        self.listen_for_response()

    def listen_for_response(self):
        """Listens for server responses."""
        try:
            self.udp_socket.settimeout(5)  # Set timeout for response
            response, _ = self.udp_socket.recvfrom(1024)  # Receive response
            response_data = json.loads(response.decode())

            if response_data["type"] == "REGISTERED":
                print(f"Registration successful: RQ# {response_data['rq#']}")
            elif response_data["type"] == "REGISTER-DENIED":
                print(f"Registration failed: {response_data.get('reason', 'Unknown error')}")
            elif response_data["type"] == "DE-REGISTERED":
                print(f"Successfully de-registered: RQ# {response_data['rq#']}")
            elif response_data["type"] == "CLIENT-LIST":
                print("\nRegistered Clients:")
                print("RQ# | Client Name | Role | UDP Port | TCP Port")
                print("------------------------------------------------")
                clients = response_data.get("clients", [])
                if isinstance(clients, list) and clients:
                    for client in clients:
                        if isinstance(client, dict):
                            print(f"{client.get('rq#', 'Unknown')} | {client.get('name', 'Unknown')} | {client.get('role', 'Unknown')} | {client.get('udp_port', 'Unknown')} | {client.get('tcp_port', 'Unknown')}")
                        else:
                            print(f"Invalid client data: {client}")
                else:
                    print("No registered clients.")
            else:
                print(f"Unknown response: {response_data}")
        except socket.timeout:
            print("No response from server, request might have failed.")
        except json.JSONDecodeError:
            print("Error decoding server response.")
        except ConnectionResetError:
            print("Connection was forcibly closed by the server.")

    def close_socket(self):
        """Closes the client socket."""
        self.udp_socket.close()
        self.tcp_socket.close()

# Run client
if __name__ == "__main__":
    try:
        client = AuctionClient()
        
        while True:
            while True:
                print("\nOptions:")
                print("1. Register")
                print("2. De-register")
                print("3. Show List of Clients")
                print("4. List an Item for Auction")
                print("5. Subscribe to an Auction")
                print("6. Unsubscribe from an Auction")
                print("7. Place a Bid")
                print("8. Exit")

                choice = input("Enter your choice: ").strip()

                if choice == "1":
                    client.send_register_request()
                elif choice == "2":
                    client.send_deregister_request()
                elif choice == "3":
                    client.request_client_list()
                elif choice == "4":
                    client.list_item()
                elif choice == "5":
                    client.subscribe_to_item()
                elif choice == "6":
                    client.unsubscribe_from_item()
                elif choice == "7":
                    client.place_bid()
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
