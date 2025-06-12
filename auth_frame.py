import tkinter as tk
from tkinter import messagebox


class AuthFrame(tk.Frame):
    """
    Authentication frame (Tkinter) for login and registration.
    Supports switching modes, user validation, and session initialization.
    """
    def __init__(self, parent, on_login_success, client):
        """
        Initializes the authentication frame UI.

        :param parent: Parent widget (MainApplication)
        :param on_login_success: Callback function executed on successful login
        :param client: Instance of the Client class for communication with server
        """
        super().__init__(parent)
        self.on_login_success = on_login_success
        self.client = client
        self.is_login_mode = True
        self.logged_in = False
        self.login = None
        self.username = None

        self.title_label = None
        self.login_entry = None
        self.username_entry = None
        self.password_entry = None
        self.auth_button = None
        self.switch_button = None
        self.logout_button = None
        self.success_label = None

        self.init_widgets()

    def init_widgets(self):
        """
        Initializes or rebuilds the authentication form UI depending on the current mode (login or registration).
        Clears all existing widgets and redraws them.
        """
        for widget in self.winfo_children():
            widget.destroy()

        self.title_label = tk.Label(self, text="Entrance", font=("Arial", 16))
        self.title_label.pack(pady=10)

        self.login_entry = tk.Entry(self)
        self.login_entry.insert(0, "Login")
        self.login_entry.pack(pady=5)

        self.username_entry = tk.Entry(self)
        if not self.is_login_mode:
            self.username_entry.insert(0, "Display Name")
            self.username_entry.pack(pady=5)

        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.insert(0, "1234")
        self.password_entry.pack(pady=5)

        self.auth_button = tk.Button(self, text="Enter", command=self.authenticate)
        self.auth_button.pack(pady=10)

        self.switch_button = tk.Button(self, text="No account? Register", command=self.switch_mode)
        self.switch_button.pack(pady=5)

        self.logout_button = tk.Button(self, text="Exit", command=self.logout)
        self.success_label = tk.Label(self, text="", font=("Arial", 12))

    def switch_mode(self):
        """
        Toggles between login and registration modes.
        Updates UI texts accordingly.
        """
        self.is_login_mode = not self.is_login_mode
        mode = "Entrance" if self.is_login_mode else "Registration"
        button_text = "No account? Register" if self.is_login_mode else "Do you already have an account? Enter"

        self.title_label.config(text=mode)
        self.auth_button.config(text="Enter" if self.is_login_mode else "Register")
        self.switch_button.config(text=button_text)
        self.init_widgets()

    def authenticate(self):
        """
        Handles both login and registration logic depending on the current mode.

        - In login mode: validates credentials and logs in user.
        - In registration mode: creates a new account and switches to log in.
        """
        login = self.login_entry.get()
        password = str(self.password_entry.get())
        username = self.username_entry.get().strip() if not self.is_login_mode else None

        if self.is_login_mode:
            try:
                self.username = self.client.login(login, password)
                if self.client.user_id and self.username:
                    self.logged_in = True
                    self.on_login_success(self.username, self.client.user_id)
                    self.show_logged_in()
                else:
                    messagebox.showerror("Error", "Invalid login or password")
            except Exception as e:
                messagebox.showerror("Error", f"Error when logging in: {e}")
        else:
            if not username:
                messagebox.showwarning("Error", "Please enter username")
                return
            try:
                self.client.sign_in(login, username, password)
                if self.client.user_id:
                    messagebox.showinfo("Success", "Registration was successful.")
                    self.switch_mode()
                else:
                    messagebox.showerror("Error", "Registration failed.")
            except Exception as e:
                messagebox.showerror("Error", f"Error during registration: {e}")

    def show_logged_in(self):
        """
        Updates the frame to display a confirmation message
        and a logout button after successful login.
        """
        for widget in self.winfo_children():
            widget.pack_forget()

        self.success_label.config(text=f"The entry is made as: {self.username}")
        self.success_label.pack(pady=10)
        self.logout_button.pack(pady=5)

    def logout(self):
        """
        Logs out the current user and resets the authentication form.
        Also resets the client connection via parent application.
        """
        try:
            self.master.reset_client()  # type: ignore
        except Exception as e:
            print(f"Error when resetting the client: {e}")

        self.logged_in = False
        self.username = None
        self.login_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.init_widgets()
