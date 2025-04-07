
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog
import threading
import socket
import json
import time

SERVER_ADDRESS = ("127.0.0.1", 5000)

# Predefined users (for easy switching)
USERS = {
    "Buyer1": "Buyer",
    "Buyer2": "Buyer",
    "Seller1": "Seller",
    "Seller2": "Seller"
}

class GUIAuctionClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Auction Client (GUI)")

        # State
        self.client_name = tk.StringVar(value="Buyer1")
        self.role = tk.StringVar(value="Buyer")
        self.rq_counter = 0
        self.running = True

        # Sockets
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("", 0))
        self.udp_port = self.udp_socket.getsockname()[1]
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(("", 0))
        self.tcp_port = self.tcp_socket.getsockname()[1]

        # GUI Layout
        self.setup_ui()

        # Background thread
        threading.Thread(target=self.listen_for_messages, daemon=True).start()

    def setup_ui(self):
        frame = tk.Frame(self.master)
        frame.pack(padx=10, pady=10)

        # User dropdown
        ttk.Label(frame, text="User:").grid(row=0, column=0)
        self.user_menu = ttk.Combobox(frame, textvariable=self.client_name, values=list(USERS.keys()))
        self.user_menu.grid(row=0, column=1)
        self.user_menu.bind("<<ComboboxSelected>>", self.update_role)

        # Register / Deregister
        ttk.Button(frame, text="Register", command=self.send_register_request).grid(row=0, column=2)
        ttk.Button(frame, text="Deregister", command=self.send_deregister_request).grid(row=0, column=3)

        # Actions
        ttk.Button(frame, text="List Item", command=self.list_item).grid(row=1, column=0)
        ttk.Button(frame, text="Subscribe", command=self.subscribe_item).grid(row=1, column=1)
        ttk.Button(frame, text="Place Bid", command=self.place_bid).grid(row=1, column=2)

        # Log Output
        self.log = scrolledtext.ScrolledText(frame, width=80, height=20, state="disabled")
        self.log.grid(row=2, column=0, columnspan=4, pady=10)

    def update_role(self, event=None):
        name = self.client_name.get()
        self.role.set(USERS.get(name, "Buyer"))

    def log_message(self, msg):
        self.log.config(state="normal")
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def next_rq(self):
        self.rq_counter += 1
        return self.rq_counter

    def send_udp(self, request):
        message = json.dumps(request).encode()
        self.udp_socket.sendto(message, SERVER_ADDRESS)

    def send_register_request(self):
        name = self.client_name.get()
        role = self.role.get()
        request = {
            "type": "REGISTER",
            "rq#": self.next_rq(),
            "name": name,
            "role": role,
            "ip": socket.gethostbyname(socket.gethostname()),
            "udp_port": self.udp_port,
            "tcp_port": self.tcp_port
        }
        self.send_udp(request)
        self.log_message(f"Sent REGISTER: {request}")

    def send_deregister_request(self):
        request = {
            "type": "DE-REGISTER",
            "rq#": self.next_rq(),
            "name": self.client_name.get()
        }
        self.send_udp(request)
        self.log_message(f"Sent DE-REGISTER: {request}")

    def list_item(self):
        if self.role.get() != "Seller":
            self.log_message("Only sellers can list items.")
            return

        item = simpledialog.askstring("Item Name", "Enter item name:")
        desc = simpledialog.askstring("Item Description", "Enter item description:")
        price = simpledialog.askfloat("Start Price", "Enter starting price:")
        duration = simpledialog.askinteger("Duration", "Enter duration (seconds):")

        if not item or not desc or not price or not duration:
            self.log_message("Listing canceled or invalid input.")
            return

        request = {
            "type": "LIST_ITEM",
            "rq#": self.next_rq(),
            "item_name": item,
            "item_description": desc,
            "start_price": price,
            "duration": duration,
            "name": self.client_name.get()
        }
        self.send_udp(request)
        self.log_message(f"Sent LIST_ITEM: {request}")

    def subscribe_item(self):
        if self.role.get() != "Buyer":
            self.log_message("Only buyers can subscribe.")
            return

        item = simpledialog.askstring("Subscribe", "Enter item name to subscribe to:")
        if not item:
            return

        request = {
            "type": "SUBSCRIBE",
            "rq#": self.next_rq(),
            "item_name": item
        }
        self.send_udp(request)
        self.log_message(f"Sent SUBSCRIBE: {request}")

    def place_bid(self):
        if self.role.get() != "Buyer":
            self.log_message("Only buyers can place bids.")
            return

        item = simpledialog.askstring("Bid", "Enter item name:")
        amount = simpledialog.askfloat("Bid Amount", "Enter bid amount:")
        rq_number = simpledialog.askinteger("RQ#", "Enter RQ# from AUCTION_ANNOUNCE:")
        if not item or not amount or not rq_number:
            return

        request = {
            "type": "BID",
            "rq#": rq_number,
            "item_name": item,
            "bid_amount": amount,
            "bidder_name": self.client_name.get()
        }
        self.send_udp(request)
        self.log_message(f"Sent BID: {request}")

    def listen_for_messages(self):
        while self.running:
            try:
                self.udp_socket.settimeout(1)
                data, _ = self.udp_socket.recvfrom(1024)
                response = json.loads(data.decode())
                self.master.after(0, self.handle_server_response, response)
            except socket.timeout:
                continue


    def handle_auction_closure_response(self, response_data):
        """Handle the WINNER, SOLD, or NON_OFFER responses."""
        msg_type = response_data.get("type")
    
        if msg_type == "WINNER":
            print(f"\nAuction won by you! {response_data['item_name']} - Final Price: {response_data['final_price']}")
            print(f"Seller: {response_data['seller_name']}")
        elif msg_type == "SOLD":
            print(f"\nItem sold! {response_data['item_name']} - Final Price: {response_data['final_price']}")
            print(f"Buyer: {response_data['buyer_name']}")
        elif msg_type == "NON_OFFER":
            print(f"\nNo bids for {response_data['item_name']}. Auction closed without sale.")


    def handle_server_response(self, data):
        msg_type = data.get("type", "UNKNOWN")
        self.log_message(f"RECV [{msg_type}]: {json.dumps(data, indent=2)}")

    def stop(self):
        self.running = False
        self.udp_socket.close()
        self.tcp_socket.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = GUIAuctionClient(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop(), root.destroy()))
    root.mainloop()
