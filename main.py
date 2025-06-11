import tkinter as tk
from tkinter import messagebox, ttk
from editor_frame import EditorFrame
from auth_frame import AuthFrame
from chat_frame import ChatFrame
from gallery_frame import GalleryFrame
from client import Client
import time
import shutil
import os

SERVER_IP = "172.18.80.1"
SERVER_PORT = 443


class MainApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image Editor")
        self.geometry("800x650")

        self.username = None
        self.user_id = None
        self.client = Client(SERVER_IP, SERVER_PORT)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Editor's tab
        self.editor_frame = EditorFrame(self)
        self.notebook.add(self.editor_frame, text="Editor")

        # Authorization tab
        self.auth_frame = AuthFrame(self, self.on_login_success, self.client)
        self.notebook.add(self.auth_frame, text="Authorization")

        # Gallery tab
        self.gallery_stub_frame = tk.Frame(self)
        self.gallery_label = tk.Label(self.gallery_stub_frame, text="Gallery (only for authorized users)")
        self.gallery_label.pack(pady=20)
        self.gallery_widget = self.gallery_stub_frame
        self.notebook.add(self.gallery_widget, text="Gallery")

        # Chat tab
        self.chats_stub_frame = tk.Frame(self)
        self.chat_label = tk.Label(self.chats_stub_frame, text="Chats (only for authorized users)")
        self.chat_label.pack(pady=20)
        self.chat_widget = self.chats_stub_frame
        self.notebook.add(self.chat_widget, text="Chats")

        self.notebook.bind("<<NotebookTabChanged>>", self.check_authentication)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_login_success(self, username, user_id):
        self.username = username
        self.user_id = user_id
        print(f"The entry is made as: {username}")

        self.notebook.forget(self.chat_widget)
        self.chat_widget = ChatFrame(self, self.client, username, user_id)
        self.client.set_chat_frame(self.chat_widget)
        self.notebook.add(self.chat_widget, text="Chats")

        self.notebook.forget(self.gallery_widget)
        self.gallery_widget = GalleryFrame(self, self.client, user_id)
        self.notebook.add(self.gallery_widget, text="Gallery")

        if hasattr(self.gallery_widget, "load_gallery"):
            self.gallery_widget.load_gallery()

    def check_authentication(self, event):
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")

        if tab_text in ["Gallery", "Chats"] and not self.username:
            tk.messagebox.showwarning("Entrance is required", "Please log in to your account for access.")
            self.notebook.select(1)
        elif tab_text == "Chats" and self.username:
            if hasattr(self.chat_widget, "load_chats"):
                self.chat_widget.load_chats()
        elif tab_text == "Gallery" and self.username:
            if hasattr(self.gallery_widget, "load_gallery"):
                self.gallery_widget.load_gallery()

    def on_close(self):
        self.reset_client()
        self.destroy()

    def reset_client(self):
        try:
            shutil.rmtree("temp_gallery_cache")
            os.makedirs("temp_gallery_cache", exist_ok=True)
            shutil.rmtree("temp_chats_cache")
            os.makedirs("temp_chats_cache", exist_ok=True)
        except Exception as e:
            print(f"Error clearing the cache: {e}")

        try:
            self.client.exit()
        except Exception as e:
            print(f"Error when resetting the client: {e}")

        time.sleep(0.1)
        self.client = Client(SERVER_IP, SERVER_PORT)
        self.auth_frame.client = self.client
        self.editor_frame.parent.client = self.client
        self.username = None

        self.notebook.forget(self.chat_widget)
        self.chat_widget = self.chats_stub_frame
        self.notebook.add(self.chat_widget, text="Chats")

        self.notebook.forget(self.gallery_widget)
        self.gallery_widget = self.gallery_stub_frame
        self.notebook.add(self.gallery_widget, text="Gallery")


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
