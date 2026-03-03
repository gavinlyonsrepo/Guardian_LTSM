"""
    One Bit Converter Module for Guardian LTSM
    This module provides functionality to convert
    between 1-bit images and raw byte data.
"""

import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk # pylint: disable=no-name-in-module
from guardian_ltsm.settings import settings


class OneBitCore:
    """
        Core logic for converting between 1-bit images and byte arrays.
        This class is independent of the GUI and can be used standalone.
    """
    def __init__(self):
        self.width = 0
        self.height = 0
        self.threshold = 128
        self.invert = False
        self.vertical_addressing = False
        self.bitmap_2d = []

    def pack_bits(self, vertical=False, swap_bits=False):
        """  Packs the 2D bitmap into a byte array
        based on the specified addressing mode."""
        result = []

        if not vertical:
            # Horizontal addressing
            bytes_per_row = (self.width + 7) // 8
            for y in range(self.height):
                for xb in range(bytes_per_row):
                    byte = 0
                    for bit in range(8):
                        x = xb * 8 + bit
                        if x < self.width and self.bitmap_2d[y][x]:
                            byte |= (1 << (7 - bit))  # MSB first
                    if swap_bits:
                        byte = int(f"{byte:08b}"[::-1], 2)
                    result.append(byte)
        else:
            # Vertical addressing - pages across width first
            bytes_per_col = (self.height + 7) // 8
            for yb in range(bytes_per_col):
                for x in range(self.width):
                    byte = 0
                    for bit in range(8):
                        y = yb * 8 + bit
                        if y < self.height and self.bitmap_2d[y][x]:
                            byte |= (1 << bit)  # LSB first
                    if swap_bits:
                        byte = int(f"{byte:08b}"[::-1], 2)
                    result.append(byte)

        return result

    def image_to_bitmap(self, pil_image):
        """ Converts a PIL image to a 2D bitmap
            based on the threshold and invert settings.
        """
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


    def bitmap_to_image(self):
        """ Converts the 2D bitmap back to a PIL image for preview or saving. """
        img = Image.new("1", (self.width, self.height))

        for y in range(self.height):
            for x in range(self.width):
                p = 255 if self.bitmap_2d[y][x] else 0
                img.putpixel((x, y), p)

        return img

    def unpack_bits(self, raw_bytes):
        """ Unpacks a byte array into the 2D bitmap based on the specified addressing mode. """
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
                            val = (byte >> (7 - bit)) & 1
                            if self.invert:
                                val ^= 1
                            self.bitmap_2d[y][x] = val
        else:
            # Vertical addressing - pages across width first
            bytes_per_col = (self.height + 7) // 8

            for yb in range(bytes_per_col):      # page first
                for x in range(self.width):      # then column
                    if index >= len(raw_bytes):
                        return
                    byte = raw_bytes[index]
                    index += 1
                    for bit in range(8):
                        y = yb * 8 + bit
                        if y < self.height:
                            val = (byte >> bit) & 1
                            if self.invert:
                                val ^= 1
                            self.bitmap_2d[y][x] = val


    def calc_data_size(self):
        """
        Issue 3 fix: calculate correct byte count based on addressing mode.
        Horizontal: ceil(width/8) * height
        Vertical:   width * ceil(height/8)
        """
        if not self.vertical_addressing:
            return ((self.width + 7) // 8) * self.height
        return self.width * ((self.height + 7) // 8)


class OneBitConverter(tk.Frame): # pylint: disable=too-many-instance-attributes,attribute-defined-outside-init
    """ `OneBitConverter` is the main GUI component 
    for converting between 1-bit images and raw byte data.
    It provides an interface for users to load images or 
    paste data, adjust settings, preview results"""

    def __init__(self, parent, controller, data_mode):
        super().__init__(parent)

        self.controller = controller
        self.data_mode = data_mode
        self.core = OneBitCore()
        self.original_image = None
        self.raw_bytes      = None
        self.preview_w = settings.getint("Display", "preview_width",  fallback=160)
        self.preview_h = settings.getint("Display", "preview_height", fallback=160)
        self.label_name       = None
        self.label_size       = None
        self.label_type       = None
        self.label_modified   = None
        self.file_info_frame  = None
        self.preview_label    = None
        self.threshold_slider = None
        self.image_name_var   = None
        self.file_name_var    = None
        self.file_type_var    = None
        self.out_addressing_var = None
        self.swap_bits_var    = None
        self.build_ui()
        if self.data_mode:
            self.open_data_dialog()
        else:
            self.open_image_dialog()

    def build_ui(self):
        """ Builds the user interface components. Called during initialization."""
        self._build_title_and_info()
        self._build_preview()
        # Always create these vars so refresh() can always read them ----
        self.threshold_var = tk.IntVar(value=128)
        self.invert_var    = tk.BooleanVar(value=False)
        self._build_settings_panels()
        self.output_button = tk.Button(self, text="Output",
                                       state="disabled", command=self.save_output)
        self.output_button.pack(pady=5)

    def _build_title_and_info(self):
        mode_text = "Data to Image" if self.data_mode else "Image to Data"
        tk.Label(self, text=mode_text, font=("Arial", 14, "bold")).pack(pady=5)
        file_info_frame = tk.LabelFrame(self, text="File Info")
        file_info_frame.pack(fill="x", padx=10, pady=10)

        # Left side: metadata
        info_left = tk.Frame(file_info_frame)
        info_left.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        self.label_name     = tk.Label(info_left, text="Name: ")
        self.label_name.pack(anchor="w")
        self.label_size     = tk.Label(info_left, text="Size: ")
        self.label_size.pack(anchor="w")
        self.label_type     = tk.Label(info_left, text="Type: ")
        self.label_type.pack(anchor="w")
        self.label_modified = tk.Label(info_left, text="Last modified: ")
        self.label_modified.pack(anchor="w")

        self.file_info_frame = file_info_frame

    def _build_preview(self):
        # Right side: image preview
        preview_right = tk.Frame(self.file_info_frame)
        preview_right.pack(side="right", padx=10, pady=5)
        tk.Label(preview_right, text="Preview").pack()
        preview_container = tk.Frame(
            preview_right,
            width=self.preview_w,
            height=self.preview_h,
            bg="white",
            relief="solid",
            bd=1
        )
        preview_container.pack()
        preview_container.pack_propagate(False)
        self.preview_label = tk.Label(
            preview_container,
            bg="white"
        )
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")

    def _build_settings_panels(self):
        # IMAGE SETTINGS (image-to-data mode only)
        if not self.data_mode:
            settings_frame = tk.LabelFrame(self, text="Image Settings")
            settings_frame.pack(fill="x", padx=10, pady=5)
            tk.Label(settings_frame, text="Threshold").pack(anchor="w", padx=5)
            self.threshold_slider = tk.Scale(
                settings_frame,
                from_=0,
                to=255,
                orient="horizontal",
                variable=self.threshold_var,        # Issue 2 fix: bind directly to var
                command=self.on_threshold_change
            )
            self.threshold_slider.pack(fill="x", padx=5)
            self.threshold_slider.set(128)
            tk.Checkbutton(
                settings_frame,
                text="Invert",
                variable=self.invert_var,
                command=self.refresh
            ).pack(anchor="w", padx=5, pady=2)
        else: # OUTPUT SETTINGS (image-to-data mode only)
            if not self.data_mode:
                out_frame = tk.LabelFrame(self, text="Output Settings")
                out_frame.pack(fill="x", padx=10, pady=5)

                # Row 1: image name and file name
                row1 = tk.Frame(out_frame)
                row1.pack(fill="x", padx=5, pady=3)
                tk.Label(row1, text="Image Name:").pack(side="left")
                self.image_name_var = tk.StringVar(value="my_image")
                tk.Entry(row1, textvariable=self.image_name_var, width=15).pack(side="left", padx=5)
                tk.Label(row1, text="File Name:").pack(side="left", padx=(10, 0))
                self.file_name_var = tk.StringVar(value="my_image")
                tk.Entry(row1, textvariable=self.file_name_var, width=15).pack(side="left", padx=5)

                # Row 2: file type
                row2 = tk.Frame(out_frame)
                row2.pack(fill="x", padx=5, pady=3)
                tk.Label(row2, text="File Type:").pack(side="left")
                self.file_type_var = tk.StringVar(value=".h")
                tk.Radiobutton(row2, text=".h",   variable=self.file_type_var,
                            value=".h" ).pack(side="left", padx=5)
                tk.Radiobutton(row2, text=".hpp", variable=self.file_type_var,
                            value=".hpp").pack(side="left", padx=5)

                # Row 3:
                row3 = tk.Frame(out_frame)
                row3.pack(fill="x", padx=5, pady=3)
                tk.Label(row3, text="Array Style:  const uint8_t name[] = {...};").pack(side="left")

                # Row 4: draw mode and swap bits
                row4 = tk.Frame(out_frame)
                row4.pack(fill="x", padx=5, pady=3)

                tk.Label(row4, text="Draw Mode:").pack(side="left")
                self.out_addressing_var = tk.StringVar(value="horizontal")
                tk.Radiobutton(row4, text="Horizontal", variable=self.out_addressing_var,
                            value="horizontal").pack(side="left", padx=5)
                tk.Radiobutton(row4, text="Vertical",   variable=self.out_addressing_var,
                            value="vertical"  ).pack(side="left", padx=5)

                self.swap_bits_var = tk.BooleanVar(value=False)
                tk.Checkbutton(row4, text="Swap Bits in Byte",
                            variable=self.swap_bits_var).pack(side="left", padx=15)

    def open_image_dialog(self):
        """ Opens a file dialog for the user to select an image file."""
        input_dir = settings.getstr("Paths", "input_dir", fallback=str(os.path.expanduser("~")))
        if not input_dir or not os.path.isdir(input_dir):
            input_dir = str(os.path.expanduser("~"))
        file_path = filedialog.askopenfilename(
            title="Open Image File",
            initialdir=input_dir,
            filetypes=[
                ("Image Files", "*.png *.bmp *.jpg *.jpeg *.gif"),
                ("All Files", "*.*")
            ]
        )
        if not file_path:
            # User cancelled — go back to main menu rather than showing blank screen
            print("User cancelled image open dialog.")
            return
        self.original_image = Image.open(file_path)
        filename      = os.path.basename(file_path)
        size_bytes    = os.path.getsize(file_path)
        modified_time = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(os.path.getmtime(file_path))
        )
        self.label_name.config(text=f"Name: {filename}")
        self.label_size.config(
            text=f"Size: {size_bytes} byte(s)\
                ({self.original_image.width}x{self.original_image.height}px)"
        )
        self.label_type.config(text=f"Type: {self.original_image.format}")
        self.label_modified.config(text=f"Last modified: {modified_time}")

        self.refresh()


    def open_data_dialog(self):
        """ Opens a dialog for the user to paste raw byte data and specify dimensions."""

        dialog = tk.Toplevel(self)
        dialog.title("Paste Raw Data")
        def on_cancel():
            print("User cancelled data input dialog.")
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        tk.Label(dialog, text="Paste Raw byte array , 0x00").pack()
        self.data_text = tk.Text(dialog, width=60, height=10)
        self.data_text.pack()
        tk.Label(dialog, text="Image Width").pack()
        self.width_entry = tk.Entry(dialog)
        self.width_entry.pack()
        tk.Label(dialog, text="Image Height").pack()
        self.height_entry = tk.Entry(dialog)
        self.height_entry.pack()
        self.addressing_var = tk.StringVar(value="horizontal")
        tk.Radiobutton(
            dialog, text="Horizontal Addressing",
            variable=self.addressing_var, value="horizontal",
        ).pack(anchor="w")
        tk.Radiobutton(
            dialog, text="Vertical Addressing",
            variable=self.addressing_var, value="vertical",
        ).pack(anchor="w")
        tk.Button(
            dialog, text="Convert to Image",
            command=lambda: self.load_data(dialog),
        ).pack(pady=5)

    def load_data(self, dialog):
        """ Parses the input data and updates the core and preview."""
        try:
            self.core.width  = int(self.width_entry.get())
            self.core.height = int(self.height_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid width/height")
            return

        self.core.vertical_addressing = self.addressing_var.get() == "vertical"
        # Parse once and store for re-use on refresh
        self.raw_bytes = self.parse_hex_string(self.data_text.get("1.0", tk.END))
        self.core.unpack_bits(self.raw_bytes)
        dialog.destroy()
        # Issue 3 fix: use calc_data_size() for correct byte count
        data_size = self.core.calc_data_size()
        self.label_name.config(text="Name: N/A")
        self.label_size.config(
            text=f"Size: {data_size} byte(s) ({self.core.width}x{self.core.height}px)"
        )
        self.label_type.config(text="Type: N/A")
        self.label_modified.config(text="Last modified: N/A")

        self.refresh()
        self.output_button.config(state="normal")

    def save_output(self):
        """" Saves the output based on the current mode:
        either as an image file or as a C/C++ header file."""
        if not self.core.bitmap_2d:
            return
        if self.data_mode:
            self._save_output_image()
        else:
            self._save_output_data()


    def _save_output_image(self):
        """Data to image path — save PNG/BMP."""
        output_dir = settings.getstr("Paths", "output_dir", fallback=str(os.path.expanduser("~")))
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = str(os.path.expanduser("~"))

        file_path = filedialog.asksaveasfilename(
            title="Save Image",
            initialdir=output_dir,
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("BMP Image", "*.bmp"),
                ("All Files", "*.*")
            ]
        )
        if not file_path:
            return

        img = self.core.bitmap_to_image()
        img.save(file_path)
        messagebox.showinfo("Saved", f"Image saved to:\n{file_path}")


    def _save_output_data(self):
        """Image to data path — save C/C++ header file."""
        output_dir = settings.getstr("Paths", "output_dir", fallback=str(os.path.expanduser("~")))
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = str(os.path.expanduser("~"))

        ext        = self.file_type_var.get()           # .h or .hpp
        vertical   = self.out_addressing_var.get() == "vertical"
        swap       = self.swap_bits_var.get()
        image_name = self.image_name_var.get().strip() or "myImage"
        file_name  = self.file_name_var.get().strip()  or "my_image"
        draw_mode  = "Vertical" if vertical else "Horizontal"
        keyword = "const"
        raw = self.core.pack_bits(vertical=vertical, swap_bits=swap)
        bytes_per_row = 16
        hex_bytes = [f"0x{b:02X}" for b in raw]
        lines = []

        for i in range(0, len(hex_bytes), bytes_per_row):
            lines.append("    " + ", ".join(hex_bytes[i:i + bytes_per_row]))
        body = ",\n".join(lines)
        # Header guard
        guard = f"{file_name.upper()}_{'HPP' if ext == '.hpp' else 'H'}"
        # Build file
        output_text = (
            f"#ifndef {guard}\n"
            f"#define {guard}\n"
            f"\n"
            f"#include <stdint.h>\n"
            f"\n"
            f"// -------------------------------------------------------\n"
            f"// Generated by Guardian LTSM - One Bit Converter\n"
            f"// Image Name  : {image_name}\n"
            f"// Dimensions  : {self.core.width} x {self.core.height} px\n"
            f"// Data Size   : {len(raw)} bytes\n"
            f"// Draw Mode   : {draw_mode}\n"
            f"// Swap Bits   : {'Yes' if swap else 'No'}\n"
            f"// Threshold   : {self.core.threshold}\n"
            f"// Inverted    : {'Yes' if self.core.invert else 'No'}\n"
            f"// -------------------------------------------------------\n"
            f"\n"
            f"{keyword} uint8_t {image_name}[] = {{\n"
            f"{body}\n"
            f"}};\n"
            f"\n"
            f"#endif // {guard}\n"
        )
        file_path = filedialog.asksaveasfilename(
            title="Save Header File",
            initialdir=output_dir,
            initialfile=file_name,
            defaultextension=ext,
            filetypes=[
                ("Header File", "*.h"),
                ("C++ Header",  "*.hpp"),
                ("All Files",   "*.*")
            ]
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output_text)
        # Also copy to clipboard for convenience
        self.clipboard_clear()
        self.clipboard_append(output_text)
        messagebox.showinfo("Saved", f"Header saved to:\n{file_path}\n\nAlso copied to clipboard.")


    def parse_hex_string(self, text):
        """ Parses a string containing hex byte values (e.g. "0x00, 0xFF, 0x1A")"""
        values = []
        tokens = text.replace(",", " ").split()
        for t in tokens:
            if t.startswith("0x") or t.startswith("0X"):
                try:
                    values.append(int(t, 16))
                except ValueError:
                    pass
        return values


    def on_threshold_change(self, val):
        """Threshold_var is already kept in sync via the Scale
        binding, but set explicitly here to be 
        safe before calling refresh"""
        self.threshold_var.set(int(float(val)))
        self.refresh()


    def refresh(self):
        """ Refreshes the preview and re-applies settings. 
        This is called whenever a setting changes 
        to update the output accordingly."""
        self.core.invert = self.invert_var.get()
        if self.original_image:
            # Path 1: image to data — threshold applies
            self.core.threshold = self.threshold_var.get()
            self.core.image_to_bitmap(self.original_image)
            self._update_preview()
            self.output_button.config(state="normal")
        elif hasattr(self, "raw_bytes"):
            # Path 2: data to image — re-unpack so invert is applied fresh
            self.core.unpack_bits(self.raw_bytes)
            self._update_preview()
            self.output_button.config(state="normal")


    def _update_preview(self):
        img = self.core.bitmap_to_image()
        # Only shrink, never enlarge — Issue 4: use settings values
        if img.width > self.preview_w or img.height > self.preview_h:
            img.thumbnail((self.preview_w, self.preview_h))
        photo = ImageTk.PhotoImage(img)
        self.preview_label.config(image=photo,
                                  width=self.preview_w,
                                  height=self.preview_h)
        self.preview_label.image = photo  # prevent garbage collection


if __name__ == "__main__":
    print("This is a module, not a standalone script.")
else:
    print("one bit image convertor module loaded.")
