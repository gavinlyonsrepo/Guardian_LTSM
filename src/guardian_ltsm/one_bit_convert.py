
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk


# ============================================================
# CORE LOGIC
# ============================================================

class OneBitCore:

    def __init__(self):
        self.width = 0
        self.height = 0
        self.threshold = 128
        self.invert = False
        self.vertical_addressing = False
        self.bitmap_2d = []

    # ---------------------------------------------------------
    def image_to_bitmap(self, pil_image):

        gray = pil_image.convert("L")
        self.width, self.height = gray.size
        self.bitmap_2d = []

        for y in range(self.height):
            row = []
            for x in range(self.width):
                pixel = gray.getpixel((x, y))
                val = 1 if pixel > self.threshold else 0
                if self.invert:
                    val ^= 1
                row.append(val)
            self.bitmap_2d.append(row)

    # ---------------------------------------------------------
    def bitmap_to_image(self):

        img = Image.new("1", (self.width, self.height))

        for y in range(self.height):
            for x in range(self.width):
                p = 255 if self.bitmap_2d[y][x] else 0
                img.putpixel((x, y), p)

        return img

    def unpack_bits(self, raw_bytes):

        self.bitmap_2d = [
            [0 for _ in range(self.width)]
            for _ in range(self.height)
        ]

        index = 0

        if not self.vertical_addressing:
            # Horizontal addressing
            bytes_per_row = (self.width + 7) // 8

            for y in range(self.height):
                for xb in range(bytes_per_row):

                    if index >= len(raw_bytes):
                        return

                    byte = raw_bytes[index]
                    index += 1

                    for bit in range(8):
                        x = xb * 8 + bit
                        if x < self.width:
                            val = (byte >> bit) & 1  # LSB first
                            if self.invert:
                                val ^= 1
                            self.bitmap_2d[y][x] = val

        else:
            # Vertical addressing
            bytes_per_col = (self.height + 7) // 8

            for x in range(self.width):
                for yb in range(bytes_per_col):

                    if index >= len(raw_bytes):
                        return

                    byte = raw_bytes[index]
                    index += 1

                    for bit in range(8):
                        y = yb * 8 + bit
                        if y < self.height:
                            val = (byte >> bit) & 1  # LSB first
                            if self.invert:
                                val ^= 1
                            self.bitmap_2d[y][x] = val


# ============================================================
# GUI FRAME
# ============================================================

class OneBitConverter(tk.Frame):

    def __init__(self, parent, controller, data_mode):
        super().__init__(parent)

        self.controller = controller
        self.data_mode = data_mode

        self.core = OneBitCore()
        self.original_image = None

        self.build_ui()

        if self.data_mode:
            self.open_data_dialog()
        else:
            self.open_image_dialog()

    # ---------------------------------------------------------
    def build_ui(self):

        # ---- TITLE ----
        mode_text = "Data to Image" if self.data_mode else "Image to Data"
        title = ttk.Label(self, text=mode_text, font=("Arial", 14, "bold"))
        title.pack(pady=5)


        # ---- PREVIEW FRAME ----
        # ==========================================================
        # FILE INFO FRAME (Preview Section Styled)
        # ==========================================================

        file_info_frame = ttk.LabelFrame(self, text="File Info")
        file_info_frame.pack(fill="x", padx=10, pady=10)

        # Left side: metadata
        info_left = ttk.Frame(file_info_frame)
        info_left.pack(side="left", fill="both", expand=True, padx=10, pady=5)

        self.label_name = ttk.Label(info_left, text="Name: ")
        self.label_name.pack(anchor="w")

        self.label_size = ttk.Label(info_left, text="Size: ")
        self.label_size.pack(anchor="w")

        self.label_type = ttk.Label(info_left, text="Type: ")
        self.label_type.pack(anchor="w")

        self.label_modified = ttk.Label(info_left, text="Last modified: ")
        self.label_modified.pack(anchor="w")

        # Right side: image preview
        preview_right = ttk.Frame(file_info_frame)
        preview_right.pack(side="right", padx=10, pady=5)

        ttk.Label(preview_right, text="Preview").pack()

        self.preview_label = tk.Label(
            preview_right,
            width=160,
            height=160,
            bg="white",
            relief="solid",
            bd=1
        )
        self.preview_label.pack_propagate(False)  # Prevent image from resizing label
        self.preview_label.pack()


        # ---- SETTINGS FRAME ----
        settings_frame = ttk.Frame(self)
        settings_frame.pack()

        # ---- IMAGE SETTINGS LABEL ----
        settings_label = ttk.Label(settings_frame, text="Image Settings", font=("Arial", 11, "bold"))
        settings_label.pack(pady=5)

        # Create variables FIRST (prevents callback crash)
        self.threshold_var = tk.IntVar(value=128)
        self.invert_var = tk.BooleanVar(value=False)

        ttk.Label(settings_frame, text="Threshold").pack()

        self.threshold_slider = ttk.Scale(
            settings_frame,
            from_=0,
            to=255,
            orient="horizontal",
            command=self.on_threshold_change
        )
        self.threshold_slider.pack(fill="x")

        # Set AFTER widget exists
        self.threshold_slider.set(128)

        ttk.Checkbutton(
            settings_frame,
            text="Invert",
            variable=self.invert_var,
            command=self.refresh
        ).pack(anchor="w")

        # ---- OUTPUT BUTTON ----
        self.output_button = ttk.Button(
            self,
            text="Output",
            state="disabled"
        )
        self.output_button.pack(pady=5)


    # ---------------------------------------------------------
    def return_to_main(self):
        self.master.destroy()

    # ---------------------------------------------------------


    def open_image_dialog(self):

        file_path = filedialog.askopenfilename(
            title="Open Image File",
            filetypes=[
                ("Image Files", "*.png *.bmp *.jpg *.jpeg *.gif"),
                ("All Files", "*.*")
            ]
        )

        if not file_path:
            return

        self.original_image = Image.open(file_path)

        # ---- Populate metadata ----
        filename = os.path.basename(file_path)
        size_bytes = os.path.getsize(file_path)
        modified_time = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(os.path.getmtime(file_path))
        )

        self.label_name.config(text=f"Name: {filename}")
        self.label_size.config(
            text=f"Size: {size_bytes} byte(s) ({self.original_image.width}x{self.original_image.height}px)"
        )
        self.label_type.config(text=f"Type: {self.original_image.format}")
        self.label_modified.config(text=f"Last modified: {modified_time}")

        self.refresh()

    # ---------------------------------------------------------
    def open_data_dialog(self):

        dialog = tk.Toplevel(self)
        dialog.title("Paste Raw Data")

        ttk.Label(dialog, text="Raw Hex Data").pack()

        self.data_text = tk.Text(dialog, width=60, height=10)
        self.data_text.pack()

        ttk.Label(dialog, text="Width").pack()
        self.width_entry = ttk.Entry(dialog)
        self.width_entry.pack()

        ttk.Label(dialog, text="Height").pack()
        self.height_entry = ttk.Entry(dialog)
        self.height_entry.pack()

        self.addressing_var = tk.StringVar(value="horizontal")

        ttk.Radiobutton(
            dialog,
            text="Horizontal Addressing",
            variable=self.addressing_var,
            value="horizontal"
        ).pack(anchor="w")

        ttk.Radiobutton(
            dialog,
            text="Vertical Addressing",
            variable=self.addressing_var,
            value="vertical"
        ).pack(anchor="w")

        ttk.Button(
            dialog,
            text="Load",
            command=lambda: self.load_data(dialog)
        ).pack(pady=5)

    # ---------------------------------------------------------
    def load_data(self, dialog):

        try:
            self.core.width = int(self.width_entry.get())
            self.core.height = int(self.height_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid width/height")
            return

        self.core.vertical_addressing = (
            self.addressing_var.get() == "vertical"
        )

        raw_bytes = self.parse_hex_string(
            self.data_text.get("1.0", tk.END)
        )

        self.core.unpack_bits(raw_bytes)

        dialog.destroy()

        self.refresh()
        self.output_button.config(state="normal")

    # ---------------------------------------------------------
    def parse_hex_string(self, text):

        values = []
        tokens = text.replace(",", " ").split()

        for t in tokens:
            if t.startswith("0x"):
                try:
                    values.append(int(t, 16))
                except ValueError:
                    pass

        return values

    # ---------------------------------------------------------
    def on_threshold_change(self, val):

        self.core.threshold = int(float(val))
        self.refresh()

    # ---------------------------------------------------------
    def refresh(self):

        # Guard against early Tk callback
        if not hasattr(self, "invert_var"):
            return

        self.core.invert = self.invert_var.get()

        if not self.data_mode and self.original_image:
            self.core.image_to_bitmap(self.original_image)

        if self.core.bitmap_2d:
            self.show_preview()
            self.output_button.config(state="normal")

    # ---------------------------------------------------------
    def show_preview(self):

        img = self.core.bitmap_to_image()

        # Thumbnail size
        max_w = 160
        max_h = 100

        scale = min(
            max_w / img.width if img.width else 1,
            max_h / img.height if img.height else 1,
            1
        )

        if scale < 1:
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.NEAREST)

        tk_img = ImageTk.PhotoImage(img)

        self.preview_label.config(image=tk_img)
        self.preview_label.image = tk_img
        
if __name__ == "__main__":
    print("This is a module, not a standalone script.")
else:
    print("image one bit Convert module loaded.")