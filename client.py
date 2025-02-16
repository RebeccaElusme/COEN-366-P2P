import socket
import json

class AuctionClient:
    def __init__(self):
        """Initialize client with user-provided information."""
        self.name = input("Enter your unique name: ").strip()
        self.role = input("Enter your role (Buyer/Seller): ").strip().capitalize()
        self.udp_port = int(input("Enter your UDP port number: "))
        self.tcp_port = int(input("Enter your TCP port number: "))

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", self.udp_port))  # Bind UDP socket
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

    def listen_for_response(self):
        """Listens for server responses."""
        try:
            self.udp_socket.settimeout(5)  # Set timeout for response
            response, _ = self.udp_socket.recvfrom(1024)  # Receive response
            response_data = json.loads(response.decode())

            if response_data["type"] == "REGISTERED":
                print(f"Registration successful: {response_data}")
            elif response_data["type"] == "REGISTER-DENIED":
                print(f"Registration failed: {response_data['reason']}")
            elif response_data["type"] == "DE-REGISTERED":
                print("Successfully de-registered.")
            else:
                print(f"Unknown response: {response_data}")
        except socket.timeout:
            print("No response from server, request might have failed.")

    def close_socket(self):
        """Closes the client socket."""
        self.udp_socket.close()

# Run client
if __name__ == "__main__":
    client = AuctionClient()
    
    while True:
        print("\nOptions:\n1. Register\n2. De-register\n3. Exit")
        choice = input("Enter your choice: ").strip()
        
        if choice == "1":
            client.send_register_request()
        elif choice == "2":
            client.send_deregister_request()
        elif choice == "3":
            print("Exiting client...")
            client.close_socket()
            break
        else:
            print("Invalid option, please try again.")
