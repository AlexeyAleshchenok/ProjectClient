import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
from editor import Editor
import numpy as np
import os
import io

RESOLUTIONS = {"360p": (480, 360),
               "480p": (640, 480),
               "720p": (1280, 720),
               "1080p": (1920, 1080),
               "1440p": (2560, 1440)}
KERNELS = {"Blur": np.array([[1, 1, 1, 1, 1], [1, 1, 1, 1, 1],
                            [1, 1, 1, 1, 1], [1, 1, 1, 1, 1], [1, 1, 1, 1, 1]], dtype=np.float32) / 25.0,
           "Sharpness": np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32),
           "Edge detection": np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]], dtype=np.float32),
           "Emboss": np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32),
           "Outline": np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float32),
           "Box Blur (3x3)": np.ones((3, 3), dtype=np.float32) / 9.0,
           "Gaussian Blur": np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=np.float32) / 16.0,
           "Light Sharpen": np.array([[0, -0.5, 0],[-0.5, 3, -0.5],[0, -0.5, 0]], dtype=np.float32)}


class EditorFrame(tk.Frame):
    """
    GUI frame for the image editor.
    Provides canvas-based image manipulation: filters, cropping, resizing, compression, undo/redo, saving, and upload.
    """
    def __init__(self, parent):
        """
        Initializes all editor widgets and tools:
        - Canvas for image display
        - Zoom and pan support
        - Tool buttons (filters, crop, compression, etc.)
        - Bottom control panel (open, save, reset, undo, redo)
        """
        super().__init__(parent)
        self.parent = parent
        self.editor = Editor()
        self.base_photo = None
        self.photo = None
        self.image_path = None

        # ===== Upper part: canvas and tools =====
        self.top_frame = tk.Frame(self)
        self.top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Working field
        self.canvas = tk.Canvas(self.top_frame, bg="lightgray", width=500, height=400)
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10, expand=True, fill=tk.BOTH)

        # Zoom
        self.zoom = 1.0
        self.min_zoom = 0.2
        self.max_zoom = 5.0

        # Offset
        self.pan_start = None
        self.offset_x = None
        self.offset_y = None

        # Crop attributes
        self.manual_crop_mode = False
        self.crop_start = None
        self.crop_rect_id = None
        self.disp_w = None
        self.disp_h = None

        # Canvas binds
        self.canvas.bind("<Button-1>", self.start_crop)
        self.canvas.bind("<B1-Motion>", self.draw_crop_rect)
        self.canvas.bind("<ButtonRelease-1>", self.finish_crop)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)
        self.canvas.bind("<Button-3>", self.pan_start_event)
        self.canvas.bind("<B3-Motion>", self.pan_move_event)

        # Right toolbar
        self.tools_frame = tk.Frame(self.top_frame, bd=2, relief=tk.GROOVE)
        self.tools_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        tk.Label(self.tools_frame, text="Tools", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        tk.Button(self.tools_frame, text="Filters", command=self.open_filters_window).pack(fill=tk.X, pady=2)
        tk.Button(self.tools_frame, text="Quality changing", command=self.open_resize_window).pack(fill=tk.X, pady=2)
        tk.Button(self.tools_frame, text="Crop", command=self.open_crop_window).pack(fill=tk.X, pady=2)
        tk.Button(self.tools_frame, text="Compression", command=self.open_compression_window).pack(fill=tk.X, pady=2)

        # ===== Bottom panel =====
        self.bottom_panel = tk.Frame(self, bd=1, relief=tk.RIDGE)
        self.bottom_panel.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        tk.Button(self.bottom_panel, text="Open the file", command=self.open_file).pack(side=tk.LEFT, padx=5)
        tk.Button(self.bottom_panel, text="Save", command=self.show_save_options).pack(side=tk.LEFT, padx=5)
        tk.Button(self.bottom_panel, text="Reset the changes", command=self.reset_changes).pack(side=tk.LEFT, padx=5)

        tk.Button(self.bottom_panel, text="Back", command=self.undo).pack(side=tk.RIGHT, padx=5)
        tk.Button(self.bottom_panel, text="Forward", command=self.redo).pack(side=tk.RIGHT)

    def open_file(self):
        """
        Opens an image file using file dialog and displays it in the editor.
        """
        filename = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if filename:
            print("File is open:", filename)
            self.image_path = filename
            self.editor.load_image(filename)
            self.display_image(self.editor.current_image)

    def display_image(self, img):
        """
        Displays the image on the canvas with scaling applied.
        Stores base thumbnail version and resets zoom/pan state.

        :param img: PIL image to display
        """
        base = img.copy()
        base.thumbnail((500, 400))
        self.disp_w, self.disp_h = base.size
        self.base_photo = ImageTk.PhotoImage(base)
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self._redraw_canvas()

    def _redraw_canvas(self):
        """
        Internal method to redraw image on the canvas,
        applying current zoom and pan offset.
        """
        if not hasattr(self, "base_photo"):
            return

        zoomed = self.editor.current_image.copy()
        w = int(self.disp_w * self.zoom)
        h = int(self.disp_h * self.zoom)
        zoomed = zoomed.resize((w, h), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(zoomed)

        self.canvas.delete("all")
        cx = self.canvas.winfo_width() // 2 + int(self.offset_x)
        cy = self.canvas.winfo_height() // 2 + int(self.offset_y)
        self.canvas.create_image(cx, cy, image=self.photo, anchor=tk.CENTER)

    def undo(self):
        """
        Undo the last editing operation.
        """
        self.editor.undo()
        self.display_image(self.editor.current_image)

    def redo(self):
        """
        Redo the last undone editing operation.
        """
        self.editor.redo()
        self.display_image(self.editor.current_image)

    def on_mousewheel(self, event):
        """
        Zooms in/out based on mouse wheel movement.
        Adjusts zoom level and keeps the cursor focus.
        """
        if event.delta > 0 or event.num == 4:
            factor = 1.1 if (event.state & 0x0004) else 1.25
        else:
            factor = 0.9 if (event.state & 0x0004) else 0.8

        new_zoom = min(self.max_zoom, max(self.min_zoom, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-3:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        mouse_x = self.canvas.canvasx(event.x) - canvas_w / 2 - self.offset_x
        mouse_y = self.canvas.canvasy(event.y) - canvas_h / 2 - self.offset_y
        scale = new_zoom / self.zoom
        self.offset_x -= mouse_x * (scale - 1)
        self.offset_y -= mouse_y * (scale - 1)

        self.zoom = new_zoom
        self._redraw_canvas()

    def pan_start_event(self, event):
        """
        Records starting point for image panning on right-click.
        """
        self.pan_start = (event.x, event.y)

    def pan_move_event(self, event):
        """
        Updates image offset based on mouse drag.
        """
        if not self.pan_start:
            return
        dx = event.x - self.pan_start[0]
        dy = event.y - self.pan_start[1]
        self.pan_start = (event.x, event.y)
        self.offset_x += dx
        self.offset_y += dy
        self._redraw_canvas()

    def reset_changes(self):
        confirm = messagebox.askyesno("Reset the changes", "Are you sure you want to reset all the changes?")
        if confirm:
            self.editor.reset()
            if self.editor.current_image:
                self.display_image(self.editor.current_image)
                print("The changes have been reset")

    def show_save_options(self):
        """
        Opens a dialog window offering save/upload options:
        to device, to gallery, or both.
        """
        window = tk.Toplevel(self)
        window.title("Save the file")
        window.geometry("300x150")
        tk.Label(window, text="Where to save the file", font=('Arial', 12)).pack(pady=10)

        tk.Button(window, text="To the device", command=lambda: self.save_choice("device", window)).pack(pady=5)
        tk.Button(window, text="To the gallery", command=lambda: self.save_choice("gallery", window)).pack(pady=5)
        tk.Button(window, text="To both", command=lambda: self.save_choice("both", window)).pack(pady=5)

    def save_choice(self, choice, window):
        """
        Handles the user’s save option selection.
        :param choice: "device", "gallery", or "both"
        :param window: The dialog window to close after selection
        """
        window.destroy()
        if not self.editor.current_image:
            messagebox.showwarning("There is no image", "First, open the image.")
            return

        if choice in ("device", "both"):
            self.save_to_device()

        if choice in ("gallery", "both"):
            self.upload_to_gallery()

    def save_to_device(self):
        """
        Saves the current image locally to disk using file dialog.
        """
        filepath = filedialog.asksaveasfilename(defaultextension=".png",
                                                filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg *.jpeg")])
        if filepath:
            try:
                self.editor.current_image.save(filepath)
                messagebox.showinfo("Success", f"The file is saved: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Couldn't save the file:\n{e}")

    def upload_to_gallery(self):
        """
        Uploads the current image to the user's gallery (server-side).
        Requires authentication.
        """
        if not self.parent.username:
            messagebox.showwarning("Entrance is required", "Log in to upload the image.")
            return

        try:
            buffer = io.BytesIO()
            self.editor.current_image.save(buffer, format='PNG')
            data = buffer.getvalue()
            filename = os.path.basename(self.image_path) if self.image_path else "image.png"
            self.parent.client.upload(filename, data)
            messagebox.showinfo("Success", "The image has been successfully uploaded to the gallery.")
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't upload image:\n{e}")

    def open_resize_window(self):
        """
        Opens a window for resizing image to a selected resolution (e.g., 720p, 1080p).
        """
        window = tk.Toplevel(self)
        window.title("Quality changing")
        tk.Label(window, text="Select a resolution:").pack(pady=5)

        var = tk.StringVar(window)
        var.set("720p")

        option = tk.OptionMenu(window, var, *RESOLUTIONS.keys())
        option.pack(pady=5)

        def apply():
            if self.editor.current_image:
                size = RESOLUTIONS[var.get()]
                self.editor.current_image = self.editor.resize_image(size)
                self.display_image(self.editor.current_image)
                window.destroy()

        tk.Button(window, text="Apply", command=apply).pack(pady=5)

    def open_compression_window(self):
        """
        Opens a window for compressing the image with a chosen quality preset.
        """
        if not self.editor.current_image:
            messagebox.showwarning("There is no image", "First, open the image.")
            return

        window = tk.Toplevel(self)
        window.title("Image compression")
        tk.Label(window, text="Select the compression ratio:").pack(pady=5)

        quality_options = {"Light": 90,
                           "Medium": 60,
                           "Strong": 30}

        var = tk.StringVar(window)
        var.set("Medium")

        option = tk.OptionMenu(window, var, *quality_options.keys())
        option.pack(pady=5)

        def apply():
            quality = quality_options[var.get()]
            compressed_img = self.editor.compress_image(quality)
            if compressed_img:
                self.editor.current_image = compressed_img
                self.display_image(self.editor.current_image)
            window.destroy()

        tk.Button(window, text="Apply", command=apply).pack(pady=5)

    def rotate_and_refresh(self, angle):
        """
        Rotates the image by a given angle and refreshes the canvas.

        :param angle: Degrees (positive for counterclockwise)
        """
        self.editor.rotate_image(angle)
        self.display_image(self.editor.current_image)

    def open_crop_window(self):
        """
        Opens cropping window with predefined aspect ratio options,
        rotation controls, and manual crop toggle.
        """
        if not self.editor.current_image:
            messagebox.showwarning("There is no image", "First, open the image.")
            return

        window = tk.Toplevel(self)
        window.title("Cropping an image")
        window.geometry("300x300")
        tk.Label(window, text="Select the aspect ratio:").pack(pady=5)

        aspect_ratios = {"1:1": (1, 1),
                         "4:3": (4, 3),
                         "3:2": (3, 2),
                         "16:9": (16, 9),
                         "9:16": (9, 16)}

        var = tk.StringVar(window)
        var.set("1:1")
        tk.OptionMenu(window, var, *aspect_ratios.keys()).pack(pady=5)

        def apply_crop():
            w, h = aspect_ratios[var.get()]
            self.editor.crop_to_aspect_ratio(w, h)
            self.display_image(self.editor.current_image)
            window.destroy()

        tk.Button(window, text="Crop", command=apply_crop).pack(pady=10)
        tk.Label(window, text="Rotate the image:").pack(pady=(20, 5))
        tk.Button(window, text="90° clockwise", command=lambda: self.rotate_and_refresh(270)).pack(pady=2)
        tk.Button(window, text="90° counterclockwise", command=lambda: self.rotate_and_refresh(90)).pack(pady=2)

        tk.Label(window, text="Manual clipping:", font=('Arial', 10, 'bold')).pack(pady=(15, 5))
        manual_btn = tk.Button(window, text="Turn on", width=15, command=lambda: toggle_manual())
        manual_btn.pack(pady=2)

        def toggle_manual():
            self.toggle_manual_crop()
            manual_btn.config(text="Turn off" if self.manual_crop_mode else "Turn on")

    def toggle_manual_crop(self):
        """
        Enables or disables manual cropping mode.
        Clears any active selection if deactivated.
        """
        self.manual_crop_mode = not self.manual_crop_mode
        if not self.manual_crop_mode:
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
                self.crop_rect_id = None
            self.crop_start = None

    def start_crop(self, event):
        """
        Mouse-down event to start drawing manual crop rectangle.
        """
        if not (self.manual_crop_mode and self.editor.current_image):
            return
        self.crop_start = (event.x, event.y)
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
            self.crop_rect_id = None

    def draw_crop_rect(self, event):
        """
        Mouse-move event to update live crop rectangle display.
        """
        if not (self.manual_crop_mode and self.crop_start):
            return
        x0, y0 = self.crop_start
        x1, y1 = event.x, event.y

        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
        self.crop_rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2)

    def finish_crop(self, event):
        """
        Mouse-release event that calculates and applies the crop based on selection.

        Converts canvas coordinates to actual image coordinates using scale and offset.
        """
        if not (self.manual_crop_mode and self.crop_start and self.editor.current_image):
            return

        x0, y0 = self.crop_start
        x1, y1 = event.x, event.y

        orig_w, orig_h = self.editor.current_image.size
        disp_w, disp_h = self.disp_w, self.disp_h

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        img_left = canvas_w // 2 - disp_w // 2 + self.offset_x
        img_top = canvas_h // 2 - disp_h // 2 + self.offset_y

        scale = disp_w / orig_w

        left = int((min(x0, x1) - img_left) / scale)
        top = int((min(y0, y1) - img_top) / scale)
        right = int((max(x0, x1) - img_left) / scale)
        bottom = int((max(y0, y1) - img_top) / scale)

        left, right = max(0, left), min(orig_w, right)
        top, bottom = max(0, top), min(orig_h, bottom)

        if right - left > 0 and bottom - top > 0:
            self.editor.crop_rect(left, top, right, bottom)
            self.display_image(self.editor.current_image)

        self.crop_start = None
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
            self.crop_rect_id = None

    def open_filters_window(self):
        """
        Opens a window to select and apply convolution filters (e.g., blur, sharpen).
        Supports combining filters or resetting before applying.
        """
        if not self.editor.current_image:
            messagebox.showwarning("There is no image", "First, open the image.")
            return

        window = tk.Toplevel(self)
        window.title("Select a filter")
        tk.Label(window, text="Apply a filter:", font=('Arial', 12)).pack(pady=10)

        var = tk.StringVar(window)
        var.set(next(iter(KERNELS)))

        option = tk.OptionMenu(window, var, *KERNELS.keys())
        option.pack(pady=5)

        mix_var = tk.BooleanVar(value=False)
        mix_check = tk.Checkbutton(window, text="Mix with previous filters", variable=mix_var)
        mix_check.pack(pady=5)

        def apply_filter():
            key = var.get()
            kernel = KERNELS[key]

            if not mix_var.get():
                self.editor.reset()
            self.editor.apply_kernel(kernel)
            self.display_image(self.editor.current_image)
            window.destroy()

        tk.Button(window, text="Apply", command=apply_filter).pack(pady=10)
