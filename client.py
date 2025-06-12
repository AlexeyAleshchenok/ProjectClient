import socket
import json
import ssl
import threading
import os
import queue
from datetime import datetime

CRT_FILE = "cert.pem"


class Client:
    """
    Represents a client that connects to the server via SSL.
    Handles sending and receiving HTTP-like requests over sockets,
    manages session state, chat logic, and user interaction.
    """
    def __init__(self, server_ip, server_port):
        """
        Initializes the SSL connection to the server and starts the receiving thread.

        :param server_ip: IP address of the server
        :param server_port: Port to connect to
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.response_queue = queue.Queue()
        self.chat_frame = None
        self.user_id = None
        self.user_login = None
        self.username = None

        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if CRT_FILE:
            self.ssl_context.load_verify_locations(CRT_FILE)

        self.raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket = self.ssl_context.wrap_socket(self.raw_socket, server_hostname=self.server_ip)
        self.client_socket.connect((self.server_ip, self.server_port))
        self.start_receiving()

    def set_chat_frame(self, chat_frame):
        """
        Sets a reference to the chat UI frame (for message display).
        :param chat_frame: An instance of ChatFrame
        """
        self.chat_frame = chat_frame

    def send_request(self, method, path, params=None, body=None):
        """
        Constructs and sends an HTTP-like request to the server.

        :param method: HTTP method ("GET", "POST")
        :param path: URL path (e.g., "/login")
        :param params: Optional URL query parameters as a dictionary
        :param body: Optional binary payload
        :return: Server response (status_code, body)
        """
        params_str = '&'.join(f'{key}={value}' for key, value in (params or {}).items())
        url = f'{path}?{params_str}' if params_str else path

        headers = {"Content-Length": str(len(body)) if body else "0"}

        request = f"{method} {url} HTTP/1.1\r\n"
        request += "\r\n".join(f"{key}: {value}" for key, value in headers.items())
        request += "\r\n\r\n"

        if body:
            request = request.encode() + body
        else:
            request = request.encode()

        self.client_socket.sendall(request)
        return self.response_queue.get()

    def start_receiving(self):
        """
        Starts a background thread to listen for incoming server messages.
        """
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _receive_loop(self):
        """
        Continuously listens for server responses.
        Parses headers and dispatches messages or enqueues regular responses.
        """
        while True:
            try:
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = self.client_socket.recv(1024)
                    if not chunk:
                        return
                    data += chunk

                headers, _, body = data.partition(b"\r\n\r\n")
                headers = headers.decode().split("\r\n")
                status_line = headers[0]

                headers_dict = {}
                for header in headers[1:]:
                    key, value = header.split(": ", 1)
                    headers_dict[key.lower()] = value

                content_length = int(headers_dict.get("content-length", 0))
                while len(body) < content_length:
                    body += self.client_socket.recv(1024)

                status = int(status_line.split(" ")[1])
                type_header = headers_dict.get("type", "response")
                if status == 200 or status == 201:
                    if type_header == "message":
                        self.handle_incoming_message(body)
                    else:
                        self.response_queue.put((status, body))
            except Exception as e:
                print("Receive error:", e)
                break

    def handle_incoming_message(self, body):
        """
        Handles real-time incoming chat messages from the server.

        :param body: Raw JSON message payload
        """
        try:
            message = json.loads(body)
            chat_id = message.get("chat_id")
            if chat_id:
                self.save_message(chat_id, message)
                sender = message.get("sender")
                content = message.get("content")
                print(f"\n[Chat {chat_id}] Message from {sender}: {content}")
                if hasattr(self, "chat_frame") and self.chat_frame.selected_chat_id == chat_id:
                    self.chat_frame.display_message(message)
        except Exception as e:
            print("Error handling incoming message:", e)

    @staticmethod
    def save_message(chat_id, message_data):
        """
        Saves a message to a local JSON file for the given chat.

        :param chat_id: ID of the chat
        :param message_data: Dict with message info
        """
        os.makedirs("chat_history", exist_ok=True)
        file_path = os.path.join("chat_history", f"chat_{chat_id}.json")

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        else:
            chat_history = []

        chat_history.append(message_data)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(chat_history, f, indent=2)

    @staticmethod
    def load_chat_history(chat_id):
        """
        Loads a saved chat history from local JSON storage.

        :param chat_id: ID of the chat
        :return: List of message dictionaries
        """
        file_path = os.path.join("chat_history", f"chat_{chat_id}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    # POST
    def login(self, login, password):
        """
        Sends login credentials to the server.
        On success, sets session user_id and returns username.

        :return: username on success, None on failure
        """
        body = (json.dumps({"login": login, "password": password})).encode()
        status, response = self.send_request("POST", "/login", body=body)

        response_data = json.loads(response)
        if status == 200:
            self.user_id = response_data.get("id")
            self.user_login = login
            self.username = response_data.get("username")
            print(response_data.get("message"))
            return self.username
        else:
            print("Login failed:", response_data.get("message"))
            return

    def sign_in(self, login, username, password):
        """
        Registers a new user with the server.
        On success, sets session information.
        """
        body = (json.dumps({"login": login, "username": username, "password": password})).encode()
        status, response = self.send_request("POST", "/sign_in", body=body)

        response_data = json.loads(response)
        if status == 201:
            self.user_id = response_data.get("id")
            self.user_login = login
            self.username = username
            print(response_data.get("message"))
        else:
            print("Sign-up failed: ", response_data.get("message"))

    def upload(self, filename, file_data):
        """
        Uploads a file to the server associated with the current user.

        :return: File path on success, None otherwise
        """
        params = {"filename": filename, "id": self.user_id}
        status, response = self.send_request("POST", "/upload", params, file_data)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get("message"))
            return f"uploads/{self.user_id}/{filename}"
        else:
            print("File upload failed: ", response_data.get("message"))

    def create_new_chat(self, chat_name, members=None):
        """
        Creates a new chat (group or private) with specified members.

        :return: New chat ID on success, None otherwise
        """
        if members is None:
            members = []
        if self.user_id not in members:
            members.append(self.user_id)

        body = json.dumps({"chat_name": chat_name, "creator_id": self.user_id, "members": members}).encode()
        status, response = self.send_request("POST", "/create_chat", body=body)

        response_data = json.loads(response)
        if status == 201:
            print(f"{response_data.get('message')}\r\nChat ID: {response_data.get('chat_id')}")
            return response_data.get("chat_id")
        else:
            print("Chat creation failed:", response_data.get("message"))
            return None

    def send_message(self, chat_id, message_type, content):
        """
        Sends a message to the specified chat.

        :param chat_id: Target chat
        :param message_type: "text" or "image"
        :param content: Message text or base64 image
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_data = {"chat_id": chat_id, "sender": self.username, "sender_id": self.user_id,
                        "message_type": message_type, "content": content, "timestamp": timestamp}
        body = json.dumps(message_data).encode()
        status, response = self.send_request("POST", "/send_message", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get('message'))
            self.save_message(chat_id, message_data)
        else:
            print("Failed to send message:", response_data.get("message"))

    def add_to_chat(self, chat_id, user_id_to_add):
        """
        Adds a user to an existing chat.
        """
        body = json.dumps({"chat_id": chat_id, "user_id": user_id_to_add}).encode()
        status, response = self.send_request("POST", "/add_to_chat", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(f"User {user_id_to_add} added to chat {chat_id} successfully!")
        else:
            print(f"Failed to add user {user_id_to_add} to chat {chat_id}:", response_data.get("message"))

    def send_friend_request(self, friend_id):
        """
        Sends a friend request to another user.

        :return: True on success, False otherwise
        """
        body = json.dumps({"user_id": self.user_id, "friend_id": friend_id}).encode()
        status, response = self.send_request("POST", "/add_friend", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get("message"))
            return True
        else:
            print("Failed to send friend request:", response_data.get("message"))
            return False

    def accept_friend_request(self, friend_id):
        """
        Accepts a friend request.

        :return: True on success, False otherwise
        """
        body = json.dumps({"user_id": self.user_id, "friend_id": friend_id}).encode()
        status, response = self.send_request("POST", "/accept_friend", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get("message"))
            return True
        else:
            print("Failed to accept friend request:", response_data.get("message"))
            return False

    def decline_friend_request(self, friend_id):
        """
        Declines a pending friend request.

        :return: True on success, False otherwise
        """
        body = json.dumps({"user_id": self.user_id, "friend_id": friend_id}).encode()
        status, response = self.send_request("POST", "/decline_friend", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get("message"))
            return True
        else:
            print("Failed to decline friend request:", response_data.get("message"))
            return False

    def remove_friend(self, friend_id):
        """
        Removes a user from friend list.
        """
        body = json.dumps({"user_id": self.user_id, "friend_id": friend_id}).encode()
        status, response = self.send_request("POST", "/remove_friend", body=body)

        response_data = json.loads(response)
        if status == 200:
            print(response_data.get("message"))
        else:
            print("Failed to remove friend:", response_data.get("message"))

    # GET
    def download(self, file_path):
        """
        Downloads a file from the server by path.

        :return: File content as bytes, or None on failure
        """
        params = {"file": file_path}
        status, body = self.send_request("GET", "/download", params)

        if status == 200:
            print("File downloaded successfully!")
            return body
        else:
            response_data = json.loads(body)
            print("File download failed: ", response_data.get("message"))
            return None

    def get_gallery(self):
        """
        Fetches the list of user's uploaded images.

        :return: List of image dicts, or empty list on error
        """
        params = {"id": self.user_id}
        status, response = self.send_request("GET", "/gallery", params)

        response_data = json.loads(response)
        if status == 200:
            print("Gallery fetched successfully!")
            return response_data.get("images", [])
        else:
            print("Failed to fetch gallery:", response_data.get("message"))
            return []

    def get_chats(self):
        """
        Fetches list of user's chats.

        :return: List of chat dicts, or empty list
        """
        params = {"id": self.user_id}
        status, response = self.send_request("GET", "/chats", params)

        response_data = json.loads(response)
        if status == 200:
            print("Chats fetched successfully!")
            return response_data.get("chats", [])
        else:
            print("Failed to fetch chats:", response_data.get("message"))
            return []

    def get_friends(self):
        """
        Retrieves the current user's friend list.

        :return: List of friends or empty list
        """
        params = {"user_id": self.user_id}
        status, response = self.send_request("GET", "/friends", params)

        response_data = json.loads(response)
        if status == 200:
            return response_data.get("friends", [])
        else:
            print("Failed to fetch friends:", response_data.get("message"))
            return []

    def get_incoming_requests(self):
        """
        Gets all incoming (pending) friend requests.

        :return: List of dicts
        """
        params = {"user_id": self.user_id}
        status, response = self.send_request("GET", "/requests_incoming", params)

        response_data = json.loads(response)
        if status == 200:
            return response_data.get("incoming", [])
        else:
            print("Failed to fetch incoming requests:", response_data.get("message"))
            return []

    def get_outgoing_requests(self):
        """
        Gets all outgoing (pending) friend requests.

        :return: List of dicts
        """
        params = {"user_id": self.user_id}
        status, response = self.send_request("GET", "/requests_outgoing", params)

        response_data = json.loads(response)
        if status == 200:
            return response_data.get("outgoing", [])
        else:
            print("Failed to fetch outgoing requests:", response_data.get("message"))
            return []

    def search_user(self, username, searcher_id):
        """
        Searches for users by partial name, excluding current user.

        :return: List of matches
        """
        params = {"username": username, "searcher_id": searcher_id}
        status, response = self.send_request("GET", "/search_user", params)

        response_data = json.loads(response)
        if status == 200:
            return response_data.get("results", [])
        else:
            print("Search failed:", response_data.get("message"))
            return []

    def exit(self):
        """
        Sends logout request and closes the connection gracefully.
        """
        params = {"id": self.user_id}
        try:
            status, response = self.send_request("GET", "/exit", params)
            response_data = json.loads(response)
            print(response_data.get("message"))
        except Exception as e:
            print("Error during logout:", e)
        finally:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            self.client_socket.close()
