import socket
import json
import sys

class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = input("Enter your unique name: ").strip()
        self.role = input("Enter your role (Buyer/Seller): ").strip().capitalize()

        # Dynamically assign UDP and TCP ports
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))  # Bind to any available UDP port
        self.udp_port = self.udp_socket.getsockname()[1]

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))  # Bind to any available TCP port
        self.tcp_port = self.tcp_socket.getsockname()[1]

        self.server_address = ("127.0.0.1", 5000)

    def send_register_request(self):
        """Sends a REGISTER request to the server."""
        request = {
            "type": "REGISTER",
            "rq#": 1,  # Unique request number
            "name": self.name,
            "role": self.role,
            "ip": socket.gethostbyname(socket.gethostname()),
            "udp_port": self.udp_port,
            "tcp_port": self.tcp_port
        }
        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        print(f"Sent REGISTER request: {request}")
        self.listen_for_response()

    def send_deregister_request(self):
        """Sends a DE-REGISTER request to the server."""
        request = {
            "type": "DE-REGISTER",
            "rq#": 2,
            "name": self.name
        }
        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        print(f"Sent DE-REGISTER request: {request}")
        self.listen_for_response()

    def request_client_list(self):
        """Sends a request to the server to get the list of registered clients."""
        request = {
            "type": "SHOW-CLIENTS",
            "rq#": 3
        }
        self.udp_socket.sendto(json.dumps(request).encode(), self.server_address)
        print("Requested list of registered clients...")
        self.listen_for_response()

    def listen_for_response(self):
        """Listens for server responses."""
        try:
            self.udp_socket.settimeout(5)
            response, _ = self.udp_socket.recvfrom(1024)
            response_data = json.loads(response.decode())

            if response_data["type"] == "REGISTERED":
                print(f"Registration successful: RQ# {response_data['rq#']}")
            elif response_data["type"] == "REGISTER-DENIED":
                print(f"Registration failed: {response_data.get('reason', 'Unknown error')} (RQ# {response_data['rq#']})")
            elif response_data["type"] == "DE-REGISTERED":
                print(f"Successfully de-registered: RQ# {response_data['rq#']}")
            elif response_data["type"] == "CLIENT-LIST":
                print("\nRegistered Clients:")
                print("RQ# | Client Name | Role | UDP Port # | TCP Port #")
                print("---------------------------------------------------")
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

    def close_socket(self):
        """Closes the client socket."""
        self.udp_socket.close()
        self.tcp_socket.close()
        print("Client socket closed.")

# Run client with proper KeyboardInterrupt handling
if __name__ == "__main__":
    try:
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

    except KeyboardInterrupt:
        print("\nClient interrupted. Closing sockets...")
        client.close_socket()
        sys.exit(0)
