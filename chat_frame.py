import tkinter as tk
from tkinter import messagebox, ttk
from typing import cast, Literal
from PIL import Image, ImageTk
from datetime import datetime
import os
import time
import threading


class ChatFrame(tk.Frame):
    """
    A Tkinter frame that displays chat functionality including:
    - Sidebar with chat list and friend tools
    - Chat area with history and message input
    - Image preview and upload from gallery
    """
    def __init__(self, parent, client, username, user_id):
        """
        Initializes the chat interface UI and member variables.

        :param parent: Main application window
        :param client: Client instance for server communication
        :param username: Current user's name
        :param user_id: Current user's ID
        """
        super().__init__(parent)
        self.username = username
        self.user_id = user_id
        self.client = client

        self.selected_chat_id = None
        self.chats = [{}]
        self._chat_id_map = {}
        self._friend_id_map = {}

        self.sidebar = None
        self.search_entry = None
        self.create_button = None
        self.chat_listbox = None
        self.chat_area = None
        self.chat_canvas = None
        self.chat_scrollbar = None
        self.message_entry = None
        self.friends_frame = None
        self.refresh_friends_button = None
        self.add_friend_button = None
        self.friend_requests_button = None

        self.init_ui()

    def init_ui(self):
        """
        Constructs all UI components of the chat frame, including:
        - Sidebar for chats and friend tools
        - Chat canvas for displaying message bubbles
        - Entry box for sending messages
        - Button for sending attachments (images)
        """
        self.sidebar = tk.Frame(self, width=250, bg="#f0f0f0")
        self.sidebar.pack(side="left", fill="y")

        self.search_entry = tk.Entry(self.sidebar)
        self.search_entry.pack(fill="x", padx=10, pady=(10, 5))
        self.search_entry.insert(0, "Search for chats...")

        self.create_button = tk.Button(self.sidebar, text="Create a chat", command=self.open_create_chat_window)
        self.create_button.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(self.sidebar, text="Friends:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)

        self.friends_frame = tk.Frame(self.sidebar, bg="#f0f0f0")
        self.friends_frame.pack(fill="x", padx=10)

        self.refresh_friends_button = tk.Button(self.sidebar, text="🔄 Update your friends list",
                                                command=self.load_friends)
        self.refresh_friends_button.pack(fill="x", padx=10, pady=(0, 10))

        self.add_friend_button = tk.Button(self.sidebar, text="➕ Add a friend", command=self.open_add_friend_window)
        self.add_friend_button.pack(fill="x", padx=10, pady=(0, 10))

        self.friend_requests_button = tk.Button(self.sidebar, text="📨 Friend requests",
                                                command=self.open_friend_requests_window)
        self.friend_requests_button.pack(fill="x", padx=10, pady=(0, 10))

        self.chat_listbox = tk.Listbox(self.sidebar)
        self.chat_listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_select)

        right_frame = tk.Frame(self, bg="white")
        right_frame.pack(side="right", fill="both", expand=True)
        chat_area_frame = tk.Frame(right_frame, bg="white")
        chat_area_frame.pack(side="top", fill="both", expand=True)

        self.chat_canvas = tk.Canvas(chat_area_frame, bg="white", borderwidth=0)
        self.chat_scrollbar = tk.Scrollbar(chat_area_frame, orient="vertical", command=self.chat_canvas.yview)
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_scrollbar.pack(side="right", fill="y")
        self.chat_canvas.pack(side="right", fill="both", expand=True)

        self.chat_area = tk.Frame(self.chat_canvas, bg="white")
        self.chat_canvas.create_window((0, 0), window=self.chat_area, anchor="nw")
        self.chat_area.bind("<Configure>",
                            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))

        input_frame = tk.Frame(right_frame, bg="white")
        input_frame.pack(side="bottom", fill="x")

        self.message_entry = tk.Entry(input_frame, font=("Arial", 11))
        self.message_entry.pack(side="left", fill="x", expand=True, padx=10, pady=5)

        send_button = tk.Button(input_frame, text="Send", command=self.send_text_message)
        send_button.pack(side="left", padx=5)

        attach_button = tk.Button(input_frame, text="📎", command=self.open_gallery_selector_for_chat)
        attach_button.pack(side="left", padx=5)

    def load_chats(self):
        """Fetches available chats from the server and displays them in the sidebar."""
        self.chats = self.client.get_chats()
        self.chat_listbox.delete(0, tk.END)
        for chat in self.chats:
            self.chat_listbox.insert(tk.END, chat["name"])

    def load_friends(self):
        """Fetches the current user's friends and their online status, and displays them."""
        for widget in self.friends_frame.winfo_children():
            widget.destroy()

        try:
            friends = self.client.get_friends()
        except Exception:
            tk.Label(self.friends_frame, text="Download error", bg="#f0f0f0", fg="red").pack(anchor="w")
            return

        for friend in friends:
            name = friend["friend_name"]
            online = friend["online"]
            status_icon = "🟢" if online else "🔴"
            status_color = "#00AA00" if online else "#AA0000"
            label = tk.Label(self.friends_frame, text=f"{status_icon} {name}", anchor="w", fg=status_color,
                             bg="#f0f0f0", font=("Arial", 9))
            label.pack(fill="x", anchor="w")

    def on_chat_select(self, event):
        """Handles chat selection from the listbox and displays its message history."""
        selection = self.chat_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        chat = self.chats[index]
        self.selected_chat_id = chat["id"]
        self.display_chat_history(self.selected_chat_id)

    def display_chat_history(self, chat_id):
        """Loads and displays all stored messages for the given chat."""
        for widget in self.chat_area.winfo_children():
            widget.destroy()

        chat_history = self.client.load_chat_history(chat_id)
        for message in chat_history:
            self.display_message(message)

    def display_message(self, message):
        """
        Displays a single message bubble (text or image) in the chat area.
        Downloads the image from server if necessary.
        """
        sender = message.get("sender", "Unknown")
        sender_id = message.get("sender_id", "")
        content = message.get("content", "")
        timestamp = message.get("timestamp")
        message_type = message.get("message_type", "text")

        is_self = sender_id == self.user_id
        anchor: Literal["e", "w"] = cast(Literal["e", "w"], "e" if is_self else "w")
        text_align: Literal["left", "right"] = cast(Literal["left", "right"], "right" if is_self else "left")
        container = tk.Frame(self.chat_area, bg="white")
        container.pack(anchor=anchor, fill="x", padx=10, pady=2)

        name_color = "#0047AB" if is_self else "#4B4B4B"
        bubble_color = "#D0E6FF" if is_self else "#F0F0F0"

        sender_label = tk.Label(container, text=f"{sender}, {timestamp}", font=("Arial", 8, "italic"), fg=name_color,
                                bg="white", anchor=anchor)
        sender_label.pack(anchor=anchor, padx=5)

        if message_type == "text":
            bubble = tk.Label(container, text=content, font=("Arial", 11), bg=bubble_color if is_self else "#F0F0F0",
                              wraplength=400, justify=text_align, padx=10, pady=5, bd=1, relief="solid")
            bubble.pack(anchor=anchor, padx=10)
        elif message_type == "image":
            cache_dir = os.path.join("temp_chats_cache", str(message.get("chat_id", "")))
            os.makedirs(cache_dir, exist_ok=True)
            temp_file_path = os.path.join(cache_dir, os.path.basename(content))

            def try_load_image():
                for _ in range(5):
                    try:
                        if not os.path.exists(temp_file_path):
                            image_data = self.client.download(content)
                            if not image_data:
                                time.sleep(0.5)
                                continue
                            with open(temp_file_path, "wb") as f:
                                f.write(image_data)

                        img = Image.open(temp_file_path)
                        img.thumbnail((300, 300))
                        photo = ImageTk.PhotoImage(img)

                        def on_ui_thread():
                            image_label = tk.Label(container, image=photo, bg="white")
                            image_label.image = photo
                            image_label.pack(anchor=anchor, padx=10)
                            self.chat_canvas.update_idletasks()
                            self.chat_canvas.yview_moveto(1.0)

                        self.chat_canvas.after(0, on_ui_thread)
                        return
                    except Exception as e:
                        print(f"Retrying image download: {e}")
                        time.sleep(0.5)

                def on_fail():
                    tk.Label(container, text="[Couldn't load image]", fg="red", bg="white").pack(anchor=anchor)
                    self.chat_canvas.update_idletasks()
                    self.chat_canvas.yview_moveto(1.0)
                self.chat_canvas.after(0, on_fail)
            threading.Thread(target=try_load_image, daemon=True).start()
            return

        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def open_create_chat_window(self):
        """
        Opens a popup window where the user can specify a chat name
        and select participants from their friend list to create a group chat.
        """
        window = tk.Toplevel(self)
        window.title("Create a new chat")
        window.grab_set()

        tk.Label(window, text="Chat name:").pack(pady=(10, 0))
        chat_name_entry = tk.Entry(window, width=30)
        chat_name_entry.pack(pady=(0, 10))

        tk.Label(window, text="Select the participants:").pack()
        friends_box = tk.Listbox(window, selectmode="multiple", width=30, height=10)
        friends_box.pack(pady=(0, 10))

        friends = self.client.get_friends()
        for index, friend in enumerate(friends):
            name = friend["friend_name"]
            fid = friend["friend_id"]
            self._friend_id_map[index] = fid
            friends_box.insert(tk.END, name)

        def create_chat():
            chat_name = chat_name_entry.get().strip()
            if not chat_name:
                messagebox.showwarning("Error", "Enter the chat name.")
                return

            selected_indices = friends_box.curselection()
            if not selected_indices:
                messagebox.showwarning("Error", "Select at least one participant.")
                return

            selected_ids = [self._friend_id_map[i] for i in selected_indices]
            chat_id = self.client.create_new_chat(chat_name, selected_ids)
            if chat_id is not None:
                messagebox.showinfo("Success", f"Chat '{chat_name}' created!")
                window.destroy()
                self.refresh_chat_list()
            else:
                messagebox.showerror("Error", "Couldn't create a chat.")

        button_frame = tk.Frame(window)
        button_frame.pack()

        tk.Button(button_frame, text="Create", command=create_chat).pack(side="left", padx=5)
        tk.Button(button_frame, text="Cancel", command=window.destroy).pack(side="right", padx=5)

    def open_add_friend_window(self):
        """
        Opens a popup window to search users by name and send friend requests.
        Shows results in a list and allows selecting one to send a request.
        """
        window = tk.Toplevel(self)
        window.title("Add a friend")
        window.grab_set()

        tk.Label(window, text="Enter the user's name:").pack(pady=(10, 0))
        search_entry = tk.Entry(window)
        search_entry.pack(padx=10, pady=5, fill="x")

        result_list = tk.Listbox(window)
        result_list.pack(padx=10, pady=5, fill="both", expand=True)
        users = [{}]

        def search_user():
            query = search_entry.get().strip()
            if not query:
                messagebox.showwarning("Error", "Enter the search query.")
                return
            result_list.delete(0, tk.END)
            nonlocal users
            users = self.client.search_user(query, self.user_id)
            if not users:
                result_list.insert(tk.END, "No users found")
                return
            for user in users:
                result_list.insert(tk.END, f"{user['username']} (ID: {user['id']})")

        def send_request():
            selection = result_list.curselection()
            if not selection:
                messagebox.showwarning("Error", "Select a user from the list.")
                return
            index = selection[0]
            if index >= len(users):
                return

            selected_user = users[index]
            to_id = selected_user["id"]
            success = self.client.send_friend_request(to_id)
            if success:
                messagebox.showinfo("Success", f"The request has been sent to the user '{selected_user['username']}'")
                window.destroy()
            else:
                messagebox.showerror("Error", "Couldn't send request.")

        button_frame = tk.Frame(window)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="🔍 Search", command=search_user).pack(side="left", padx=5)
        tk.Button(button_frame, text="➕ Add to Friends", command=send_request).pack(side="right", padx=5)

    def open_friend_requests_window(self):
        """
        Opens a tabbed popup window showing incoming and outgoing friend requests.
        Allows accepting or declining incoming requests.
        """
        window = tk.Toplevel(self)
        window.title("Friend requests")
        window.geometry("400x400")
        window.grab_set()

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True)

        incoming_frame = ttk.Frame(notebook)
        notebook.add(incoming_frame, text="Incoming")
        incoming_list = tk.Listbox(incoming_frame)
        incoming_list.pack(padx=10, pady=10, fill="both", expand=True)

        outgoing_frame = ttk.Frame(notebook)
        notebook.add(outgoing_frame, text="Outgoing")
        outgoing_list = tk.Listbox(outgoing_frame)
        outgoing_list.pack(padx=10, pady=10, fill="both", expand=True)

        incoming_users = [{}]
        outgoing_users = [{}]

        def refresh_lists():
            nonlocal incoming_users, outgoing_users
            incoming_users = self.client.get_incoming_requests()
            outgoing_users = self.client.get_outgoing_requests()

            incoming_list.delete(0, tk.END)
            for user in incoming_users:
                incoming_list.insert(tk.END, f"{user['username']} (ID: {user['id']})")

            outgoing_list.delete(0, tk.END)
            for user in outgoing_users:
                outgoing_list.insert(tk.END, f"{user['username']} (ID: {user['id']})")

        def accept_selected():
            selection = incoming_list.curselection()
            if not selection:
                return
            user = incoming_users[selection[0]]
            success = self.client.accept_friend_request(user["id"])
            if success:
                messagebox.showinfo("Success", f"You are now friends with {user['username']}")
            else:
                messagebox.showerror("Error", "Couldn't accept the request.")
            refresh_lists()

        def decline_selected():
            selection = incoming_list.curselection()
            if not selection:
                return
            user = incoming_users[selection[0]]
            success = self.client.decline_friend_request(user["id"])
            if success:
                messagebox.showinfo("Declined", f"Request from {user['username']} declined.")
            else:
                messagebox.showerror("Error", "The request could not be declined.")
            refresh_lists()

        button_frame = tk.Frame(incoming_frame)
        button_frame.pack(pady=(0, 10))
        tk.Button(button_frame, text="✅ Accept", command=accept_selected).pack(side="left", padx=10)
        tk.Button(button_frame, text="❌ Decline", command=decline_selected).pack(side="left", padx=10)
        refresh_lists()

    def refresh_chat_list(self):
        """Reloads chat list and maps indexes to chat IDs."""
        self.chat_listbox.delete(0, tk.END)
        self.chats = self.client.get_chats()

        for index, chat in enumerate(self.chats):
            self._chat_id_map[index] = chat["id"]
            self.chat_listbox.insert(tk.END, chat["name"])

    def send_text_message(self):
        """
        Sends a plain text message to the selected chat.
        Also displays the message locally.
        """
        content = self.message_entry.get().strip()
        if not content or not self.selected_chat_id:
            return

        self.client.send_message(self.selected_chat_id, "text", content)
        self.message_entry.delete(0, tk.END)
        self.display_message({"sender": self.username, "sender_id": self.user_id, "message_type": "text",
                              "content": content, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

    def open_gallery_selector_for_chat(self):
        """
        Opens a gallery image picker window that shows all cached images.
        User can click on any image to send it to the currently selected chat.
        """
        cache_dir = "temp_gallery_cache"
        if not os.path.exists(cache_dir):
            messagebox.showinfo("The gallery is empty", "There are no images in the gallery cache.")
            return

        image_files = [f for f in os.listdir(cache_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if not image_files:
            messagebox.showinfo("The gallery is empty", "There are no images in the gallery cache.")
            return

        selector = tk.Toplevel(self)
        selector.title("Select an image to send")
        selector.geometry("650x500")
        selector.grab_set()

        canvas = tk.Canvas(selector)
        scrollbar = ttk.Scrollbar(selector, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, filename in enumerate(image_files):
            image_path = os.path.join(cache_dir, filename)
            server_path = f"uploads/{self.user_id}/{filename}"
            self.display_gallery_thumbnail(scrollable_frame, i, filename, image_path, server_path, selector)

    def display_gallery_thumbnail(self, parent, index, filename, image_path, server_path, selector_window):
        """
        Helper function to render a single image thumbnail inside the gallery selector.
        Binds click event to send the image to the chat.

        :param parent: Parent frame to insert the thumbnail
        :param index: Position in the grid
        :param filename: Display name
        :param image_path: Local cached path
        :param server_path: Server-side image path to send
        :param selector_window: Reference to close the selector after sending
        """
        try:
            image = Image.open(image_path)
            image.thumbnail((150, 150))
            thumbnail = ImageTk.PhotoImage(image)

            frame = ttk.Frame(parent)
            frame.grid(row=index // 4, column=index % 4, padx=10, pady=10)

            label = tk.Label(frame, image=thumbnail)
            label.image = thumbnail
            label.pack()

            def send_to_chat(event):
                if not self.selected_chat_id:
                    messagebox.showwarning("Error", "Select a chat.")
                    return
                self.client.send_message(self.selected_chat_id, "image", server_path)
                self.display_message({"chat_id": self.selected_chat_id, "sender": self.username,
                                      "sender_id": self.user_id, "message_type": "image", "content": server_path,
                                      "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                selector_window.destroy()

            label.bind("<Button-1>", send_to_chat)

            caption = tk.Label(frame, text=filename, wraplength=120)
            caption.pack()
        except Exception as e:
            print(f"Error loading the preview: {e}")
