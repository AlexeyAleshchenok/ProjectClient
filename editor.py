import numpy as np
from numpy.lib.stride_tricks import as_strided
from PIL import Image
from io import BytesIO

RED_CHANNEL = 0
GREEN_CHANNEL = 1
BLUE_CHANNEL = 2


class Editor:
    """
    Provides image processing functionality:
    loading, resizing, cropping, rotating, compressing,
    applying filters, and undo/redo stack management.
    """
    def __init__(self):
        """
        Initializes the editor state.
        Sets up original/current images and undo/redo history stacks.
        """
        self.original_image = None
        self.current_image = None
        self.undo_stack = []
        self.redo_stack = []

    def load_image(self, path):
        """
        Loads an image from file and initializes editing state.

        :param path: Path to image file
        :return: Loaded image (PIL object)
        """
        self.original_image = Image.open(path).convert("RGB")
        self.current_image = self.original_image.copy()
        self.undo_stack.clear()
        self.redo_stack.clear()
        return self.current_image

    def reset(self):
        """
        Resets the current image to the original loaded version.
        """
        if self.original_image:
            self.current_image = self.original_image.copy()

    def undo(self):
        """
        Reverts the last editing operation using undo stack.
        """
        if self.undo_stack:
            self.redo_stack.append(self.current_image.copy())
            self.current_image = self.undo_stack.pop()

    def redo(self):
        """
        Reapplies the last undone operation using redo stack.
        """
        if self.redo_stack:
            self.undo_stack.append(self.current_image.copy())
            self.current_image = self.redo_stack.pop()

    def compress_image(self, quality):
        """
        Compresses the current image into JPEG format at given quality.

        :param quality: Compression quality (0–100)
        :return: Compressed image as PIL object
        """
        if not self.current_image:
            return None

        buffer = BytesIO()
        self.current_image.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)
        compressed_image = Image.open(buffer)
        return compressed_image

    def resize_image(self, target_size):
        """
        Resizes the image while maintaining the aspect ratio.

        :param target_size: (width, height) tuple representing target size
        :return: Resized image as PIL object
        """
        if not self.current_image:
            return None

        original_width, original_height = self.current_image.size
        target_width, target_height = target_size

        # Maintain aspect ratio
        original_ratio = original_width / original_height
        target_ratio = target_width / target_height

        if target_ratio > original_ratio:
            new_height = target_height
            new_width = int(original_ratio * new_height)
        else:
            new_width = target_width
            new_height = int(new_width / original_ratio)

        # Convert to NumPy array
        np_img = np.array(self.current_image)
        # Resize using bilinear interpolation
        resized = self.bi_linear_resize(np_img, (new_height, new_width))
        return Image.fromarray(resized)

    def bi_linear_resize(self, image, new_size):
        """
        Resizes an image using bilinear interpolation (manual NumPy implementation).

        :param image: Input image as NumPy array
        :param new_size: (height, width) for resized image
        :return: Resized NumPy array
        """
        old_h, old_w, channels = image.shape
        new_h, new_w = new_size

        # Create evenly spaced coordinate grid for new size
        x = np.linspace(0, old_w - 1, new_w)
        y = np.linspace(0, old_h - 1, new_h)
        x_grid, y_grid = np.meshgrid(x, y)

        # Compute integer coordinate pairs surrounding each point
        x1 = np.floor(x_grid).astype(int)
        y1 = np.floor(y_grid).astype(int)
        x2 = np.clip(x1 + 1, 0, old_w - 1)
        y2 = np.clip(y1 + 1, 0, old_h - 1)

        new_image = np.zeros((new_h, new_w, channels), dtype=np.uint8)
        x_list = [x1, x2, x_grid]
        y_list = [y1, y2, y_grid]

        # Interpolate each channel separately
        new_image[:, :, RED_CHANNEL] = self.interpolate_channel(x_list, y_list, RED_CHANNEL, image)
        new_image[:, :, GREEN_CHANNEL] = self.interpolate_channel(x_list, y_list, GREEN_CHANNEL, image)
        new_image[:, :, BLUE_CHANNEL] = self.interpolate_channel(x_list, y_list, BLUE_CHANNEL, image)

        return new_image

    @staticmethod
    def interpolate_channel(x_list, y_list, channel, image):
        """
        Performs bilinear interpolation for a single channel of the image.

        :param x_list: List of x1, x2, and interpolated x grid
        :param y_list: List of y1, y2, and interpolated y grid
        :param channel: Channel index (R=0, G=1, B=2)
        :param image: Original image array
        :return: Interpolated 2D array of values for the specified channel
        """
        # dx and dy are the distances from the top-left pixel (x1, y1)
        dx = x_list[2] - x_list[0]
        dy = y_list[2] - y_list[0]

        # Extract the 4 neighboring pixel values for interpolation
        q11 = image[y_list[0], x_list[0], channel]
        q12 = image[y_list[1], x_list[0], channel]
        q21 = image[y_list[0], x_list[1], channel]
        q22 = image[y_list[1], x_list[1], channel]

        # Interpolate along x (left-right) then y (top-bottom)
        r1 = q11 * (1 - dx) + q21 * dx
        r2 = q12 * (1 - dx) + q22 * dx
        return np.round(r1 * (1 - dy) + r2 * dy)

    def crop_to_aspect_ratio(self, ratio_width, ratio_height):
        """
        Crops the image to fit a specific aspect ratio, centered.

        :param ratio_width: Desired aspect ratio width
        :param ratio_height: Desired aspect ratio height
        """
        if not self.current_image:
            return

        img = self.current_image
        width, height = img.size
        target_ratio = ratio_width / ratio_height
        current_ratio = width / height

        if current_ratio > target_ratio:
            new_width = int(height * target_ratio)
            offset = (width - new_width) // 2
            box = (offset, 0, offset + new_width, height)
        else:
            new_height = int(width / target_ratio)
            offset = (height - new_height) // 2
            box = (0, offset, width, offset + new_height)

        self.current_image = img.crop(box)

    def crop_rect(self, left, top, right, bottom):
        """
        Crops the image to a specified rectangular region.

        :param left: Left X coordinate
        :param top: Top Y coordinate
        :param right: Right X coordinate
        :param bottom: Bottom Y coordinate
        """
        if not self.current_image:
            return

        width, height = self.current_image.size
        left = max(0, min(left, width))
        right = max(0, min(right, width))
        top = max(0, min(top, height))
        bottom = max(0, min(bottom, height))

        if right > left and bottom > top:
            self.current_image = self.current_image.crop((left, top, right, bottom))

    def rotate_image(self, angle):
        """
        Rotates the image by a given angle (degrees), expanding the canvas to fit.

        :param angle: Angle in degrees (positive = counterclockwise)
        """
        if not self.current_image:
            return
        self.current_image = self.current_image.rotate(angle, expand=True)

    def apply_kernel(self, kernel):
        """
        Applies a convolution kernel to the image (e.g., blur, sharpen, edge-detect).

        :param kernel: 2D NumPy array defining the filter
        """
        if not self.current_image:
            return

        # Convert PIL image to NumPy array of float32
        img = np.array(self.current_image, dtype=np.float32)
        # Flip the kernel (convolution definition)
        kernel = np.flipud(np.fliplr(kernel))

        h, w, c = img.shape  # Get image height, width, and channels
        kh, kw = kernel.shape  # Kernel dimensions
        pad_h, pad_w = kh // 2, kw // 2  # Padding needed for same output size

        # Pad the image to handle borders (reflect padding)
        padded = np.pad(img, ((pad_h, pad_h), (pad_w, pad_w), (0, 0)), mode="reflect")  # type: ignore

        # Create sliding windows over the image using stride tricks
        shape = (h, w, kh, kw, c)
        strides = (padded.strides[0],  # Row stride
                   padded.strides[1],  # Column stride
                   padded.strides[0],  # Kernel row stride
                   padded.strides[1],  # Kernel column stride
                   padded.strides[2])  # Channel stride
        windows = as_strided(padded, shape=shape, strides=strides)

        # Perform convolution: dot product of image window and kernel for each pixel
        result = np.tensordot(windows, kernel, axes=([2, 3], [0, 1]))
        # Clip the values and convert to 8-bit unsigned integers
        result = np.clip(result, 0, 255).astype(np.uint8)
        # Convert result back to PIL image
        self.current_image = Image.fromarray(result)
