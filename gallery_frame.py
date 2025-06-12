import os
import tkinter as tk
from tkinter import ttk, Toplevel, Label, messagebox
from PIL import Image, ImageTk


class GalleryFrame(tk.Frame):
    """
    Gallery tab that displays user's uploaded images in a scrollable grid.
    Supports downloading thumbnails, opening images full screen, and sending them to chats.
    """
    def __init__(self, parent, client, user_id):
        """
        Initializes the gallery UI with a scrollable canvas,
        thumbnail grid layout, and local cache directory.

        :param parent: Parent widget (usually MainApplication)
        :param client: Instance of Client for server communication
        :param user_id: Current user's ID for identifying image ownership
        """
        super().__init__(parent)
        self.client = client
        self.user_id = user_id
        self.cache_dir = "temp_gallery_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.thumbnail_size = (150, 150)

    def load_gallery(self):
        """
        Fetches the user's image list from the server and displays them as thumbnails.
        Clears previous content before loading.
        """
        files = self.client.get_gallery()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for i, file_info in enumerate(files):
            name = file_info["name"]
            path = file_info["path"]
            cached_path = self.download_and_cache(path, name)
            if cached_path:
                self.display_thumbnail(i, name, cached_path)

    def download_and_cache(self, file_path, filename):
        """
        Downloads the image from the server if it's not already cached locally.

        :param file_path: Remote path to image on the server
        :param filename: Local filename to store
        :return: Local file path if successful, None otherwise
        """
        local_path = os.path.join(self.cache_dir, filename)
        if os.path.exists(local_path):
            return local_path

        file_data = self.client.download(file_path)
        if file_data is None:
            return None

        with open(local_path, "wb") as f:
            f.write(file_data)

        return local_path

    def display_thumbnail(self, index, filename, image_path):
        """
        Displays a single image thumbnail with filename caption.
        Left-click opens full screen view, right-click opens send-to-chat menu.

        :param index: Position in the thumbnail grid
        :param filename: Name of the file
        :param image_path: Local path to the image
        """
        try:
            image = Image.open(image_path)
            image.thumbnail(self.thumbnail_size)
            thumbnail = ImageTk.PhotoImage(image)

            frame = ttk.Frame(self.scrollable_frame)
            frame.grid(row=index // 4, column=index % 4, padx=10, pady=10)

            label = Label(frame, image=thumbnail)
            label.image = thumbnail
            label.pack()
            label.bind("<Button-1>", lambda e: self.open_full_screen(image_path))
            label.bind("<Button-3>", lambda e: self.open_send_menu(filename))

            caption = Label(frame, text=filename, wraplength=120)
            caption.pack()
        except Exception as ex:
            print(f"Error during uploading {filename}: {ex}")

    def open_full_screen(self, image_path):
        """
        Opens the selected image in a new full screen Toplevel window.

        :param image_path: Local path to the image to display
        """
        try:
            img = Image.open(image_path)
            win = Toplevel(self)
            win.title("Viewing")
            win.geometry("800x600")

            screen_image = ImageTk.PhotoImage(img)
            label = Label(win, image=screen_image)
            label.image = screen_image
            label.pack(expand=True, fill="both")
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't open the image: {e}")

    def open_send_menu(self, filename):
        """
        Opens a dialog to select a chat and send the selected image to it.

        :param filename: Name of the image to send
        """
        try:
            top = Toplevel(self)
            top.title("Send to the chat")
            top.geometry("300x150")

            label = Label(top, text="Select a chat:")
            label.pack(pady=5)

            chat_list = self.client.get_chats()
            chat_names = [f"{c['name']}" for c in chat_list]
            chat_ids = [c['chat_id'] for c in chat_list]

            selected = tk.StringVar()
            dropdown = ttk.Combobox(top, values=chat_names, textvariable=selected, state="readonly")
            dropdown.pack(pady=5)

            def send():
                idx = dropdown.current()
                if idx == -1:
                    messagebox.showwarning("Warning", "Select a chat.")
                    return
                chat_id = chat_ids[idx]
                image_url = f"uploads/{self.user_id}/{filename}"
                self.client.send_message(chat_id, "image", image_url)
                messagebox.showinfo("Success", "Image sent.")
                top.destroy()

            send_btn = ttk.Button(top, text="Send", command=send)
            send_btn.pack(pady=10)
        except Exception as e:
            messagebox.showerror("Error", f"Error during sending: {e}")
