import socket
import json

class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = input("Enter your unique name: ").strip()
        self.role = input("Enter your role (Buyer/Seller): ").strip().capitalize()

        # Dynamically assign UDP and TCP ports
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))  # Bind to any available UDP port
        self.udp_port = self.udp_socket.getsockname()[1]  # Get the assigned UDP port

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))  # Bind to any available TCP port
        self.tcp_port = self.tcp_socket.getsockname()[1]  # Get the assigned TCP port

        self.server_address = ("127.0.0.1", 5000)  # Change to actual server IP if needed

    def send_register_request(self):
        """Sends a REGISTER request to the server."""
        request = {
            "type": "REGISTER",
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

    def listen_for_response(self):
        """Listens for server responses."""
        try:
            self.udp_socket.settimeout(5)  # Set timeout for response
            response, _ = self.udp_socket.recvfrom(1024)  # Receive response
            response_data = json.loads(response.decode())

            if response_data["type"] == "REGISTERED":
                print(f"Registration successful: {response_data}")
            elif response_data["type"] == "REGISTER-DENIED":
                print(f"Registration failed: {response_data.get('reason', 'Unknown error')}")
            elif response_data["type"] == "DE-REGISTERED":
                print("Successfully de-registered.")
            elif response_data["type"] == "CLIENT-LIST":
                print("\nRegistered Clients:")
                print("Client Name | Role | UDP Port # | TCP Port #")
                print("--------------------------------------------")
                clients = response_data.get("clients", [])
                if isinstance(clients, list) and clients:
                    for client in clients:
                        if isinstance(client, dict):
                            print(f"{client.get('name', 'Unknown')} | {client.get('role', 'Unknown')} | {client.get('udp_port', 'Unknown')} | {client.get('tcp_port', 'Unknown')}")
                        else:
                            print(f"Invalid client data: {client}")
                elif isinstance(clients, str):  # If the server returns a message instead of a list
                    print(clients)
                else:
                    print("No registered clients.")
            else:
                print(f"Unknown response: {response_data}")
        except socket.timeout:
            print("No response from server, request might have failed.")
        except json.JSONDecodeError:
            print("Error decoding server response.")

    def close_socket(self):
        """Closes the client socket."""
        self.udp_socket.close()
        self.tcp_socket.close()

# Run client
if __name__ == "__main__":
    client = AuctionClient()
    
    while True:
        print("\nOptions:\n1. Register\n2. De-register\n3. Show List of Clients\n4. Exit")
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            client.send_register_request()
        elif choice == "2":
            client.send_deregister_request()
        elif choice == "3":
            client.request_client_list()
        elif choice == "4":
            print("Exiting client...")
            client.close_socket()
            break
        else:
            print("Invalid option, please try again.")
