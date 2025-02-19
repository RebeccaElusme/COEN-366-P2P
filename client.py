import socket
import json
import re
import sys

class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = self.get_valid_name()
        self.role = self.get_valid_role()
        self.request_counter = 0  # Track unique RQ# for requests

        # Assign UDP port dynamically
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))
        self.udp_port = self.udp_socket.getsockname()[1]

        self.server_address = ("127.0.0.1", 5000)

    def get_valid_name(self):
        while True:
            name = input("Enter your unique name: ").strip()
            if not name or not re.match("^[A-Za-z]+$", name):
                print("Invalid name. Only letters are allowed.")
            else:
                return name

    def get_valid_role(self):
        while True:
            role = input("Enter your role (Buyer/Seller): ").strip().capitalize()
            if role not in ["Buyer", "Seller"]:
                print("Invalid role. Must be Buyer or Seller.")
            else:
                return role

    def get_next_rq(self):
        self.request_counter += 1
        return self.request_counter

    def send_request(self, request_type, extra_data={}):
        """Send a request to the server with proper RQ#."""
        request = {
            "type": request_type,
            "rq#": self.get_next_rq(),
            "name": self.name,
            "role": self.role,
            "ip": socket.gethostbyname(socket.gethostname()),  # Local IP
            "udp_port": self.udp_port,
            **extra_data
        }
        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        self.listen_for_response()

    def listen_for_response(self):
        """Listens for server responses."""
        try:
            self.udp_socket.settimeout(5)
            response, _ = self.udp_socket.recvfrom(1024)
            response_data = json.loads(response.decode())
            print(f"Server Response: {response_data}")
        except socket.timeout:
            print("No response from server.")
        except json.JSONDecodeError:
            print("Error decoding server response.")

    def close_socket(self):
        """Closes the client socket."""
        self.udp_socket.close()

if __name__ == "__main__":
    client = AuctionClient()

    while True:
        print("\nOptions:\n1. Register\n2. De-register\n3. Show List of Clients\n4. Exit")
        choice = input("Enter your choice: ").strip()

        if choice == "1":
            client.send_request("REGISTER")
        elif choice == "2":
            client.send_request("DE-REGISTER")
        elif choice == "3":
            client.send_request("SHOW-CLIENTS")
        elif choice == "4":
            print("Exiting client...")
            client.close_socket()
            sys.exit(0)
        else:
            print("Invalid option, please try again.")
