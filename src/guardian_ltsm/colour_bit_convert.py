"""
    Color Bit Converter Module for Guardian LTSM
    This module provides functionality to convert
    color images into byte data.
"""

import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from dataclasses import dataclass
from PIL import Image, ImageTk # pylint: disable=no-name-in-module
from guardian_ltsm.settings import settings


LANCZOS = Image.Resampling.LANCZOS  # pylint: disable=no-member



@dataclass
class FormatOptions:
    """Options for formatting raw bytes into a C array string."""
    output_format:  str
    datatype:       str
    image_name:     str
    multiline:      bool
    separate_bytes: bool
    palette_mode:   str


class ColourBitConverter(tk.Frame): # pylint: disable=too-many-instance-attributes,attribute-defined-outside-init
    """ `ColourBitConverter` is the main GUI component
    for converting color images into raw byte data.
    It provides an interface for users to load images or
    paste data, adjust settings, preview results"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        print("Initializing ColourBitConverter...")
        self.controller = controller
        self.original_image = None
        self.raw_bytes      = None
        self.preview_w = settings.getint("Display", "preview_width",  fallback=160)
        self.preview_h = settings.getint("Display", "preview_height", fallback=160)
        self.label_name         = None
        self.label_size         = None
        self.label_type         = None
        self.label_modified     = None
        self.file_info_frame    = None
        self.preview_label      = None
        self.image_name_var     = None
        self.palette_var        = None
        self.resize_w_var       = None
        self.resize_h_var       = None
        self.output_format_var  = None
        self.endian_var         = None
        self.datatype_var       = None
        self.multiline_var      = None
        self.separate_bytes_var = None
        self.convert_button     = None
        self.copy_btn           = None
        self.save_file_btn      = None
        self.save_img_btn       = None
        self.data_text          = None
        self.converted_preview_label = None
        self.output_text        = None
        self.core = ColourBitCore()
        self.build_ui()
        self.open_image_dialog()


    def build_ui(self):
        """ Builds the user interface components. Called during initialization."""
        self._build_title_and_info()
        self._build_preview()
        self._build_settings_panels()
        self._build_output_panel()


    def _build_title_and_info(self):
        tk.Label(self, text="Colour image file conversion ",
                 font=("Arial", 14, "bold")).pack(pady=5)
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
        """Builds the conversion settings panel."""

        settings_frame = tk.LabelFrame(self, text="Conversion Settings")
        settings_frame.pack(fill="x", padx=10, pady=5)

        # ---- Row 1: Palette mode ----
        row1 = tk.Frame(settings_frame)
        row1.pack(fill="x", padx=5, pady=3)
        tk.Label(row1, text="Palette Mode:").pack(side="left")
        self.palette_var = tk.StringVar(value="RGB565")
        palette_options = [
            ("8-bit Greyscale",       "L"),
            ("16-bit RGB565",         "RGB565"),
            ("24-bit RGB",            "RGB"),
            ("32-bit RGBA",           "RGBA"),
        ]
        for label, value in palette_options:
            tk.Radiobutton(
                row1, text=label,
                variable=self.palette_var, value=value
            ).pack(side="left", padx=5)

        # ---- Row 2: Resize ----
        row2 = tk.Frame(settings_frame)
        row2.pack(fill="x", padx=5, pady=3)
        tk.Label(row2, text="Resize:").pack(side="left")
        self.resize_w_var = tk.StringVar(value="")
        self.resize_h_var = tk.StringVar(value="")
        tk.Entry(row2, textvariable=self.resize_w_var, width=6).pack(side="left", padx=3)
        tk.Label(row2, text="x").pack(side="left")
        tk.Entry(row2, textvariable=self.resize_h_var, width=6).pack(side="left", padx=3)
        tk.Label(row2, text="(fill one only to maintain aspect ratio)").pack(side="left", padx=5)

        # ---- Row 3: Output format ----
        row3 = tk.Frame(settings_frame)
        row3.pack(fill="x", padx=5, pady=3)
        tk.Label(row3, text="Output Format:").pack(side="left")
        self.output_format_var = tk.StringVar(value="hex")
        tk.Radiobutton(row3, text="Hex (0x00)",
                       variable=self.output_format_var, value="hex"    ).pack(side="left", padx=5)
        tk.Radiobutton(row3, text="Decimal",
                       variable=self.output_format_var, value="decimal").pack(side="left", padx=5)
        tk.Radiobutton(row3, text="Binary (0b000...)",
                       variable=self.output_format_var, value="binary" ).pack(side="left", padx=5)

        # ---- Row 4: Endianness ----
        row4 = tk.Frame(settings_frame)
        row4.pack(fill="x", padx=5, pady=3)
        tk.Label(row4, text="Endianness:").pack(side="left")
        self.endian_var = tk.StringVar(value="little")
        tk.Radiobutton(row4, text="Little-endian",
                       variable=self.endian_var, value="little").pack(side="left", padx=5)
        tk.Radiobutton(row4, text="Big-endian",
                       variable=self.endian_var, value="big"   ).pack(side="left", padx=5)

        # ---- Row 5: Data type and multi-line ----
        row5 = tk.Frame(settings_frame)
        row5.pack(fill="x", padx=5, pady=3)
        tk.Label(row5, text="Data Type:").pack(side="left")
        self.datatype_var = tk.StringVar(value="uint8_t")
        data_types = ["byte", "uint8_t", "uint16_t", "uint32_t"]
        tk.OptionMenu(row5, self.datatype_var, *data_types).pack(side="left", padx=5)

        self.multiline_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row5, text="Multi-line",
                       variable=self.multiline_var).pack(side="left", padx=15)

        self.separate_bytes_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row5, text="Separate bytes of pixels",
                       variable=self.separate_bytes_var).pack(side="left", padx=5)

        # ---- Row 6: Image name + Convert button ----
        row6 = tk.Frame(settings_frame)
        row6.pack(fill="x", padx=5, pady=3)
        tk.Label(row6, text="Image Name:").pack(side="left")
        self.image_name_var = tk.StringVar(value="my_image")
        tk.Entry(row6, textvariable=self.image_name_var, width=20).pack(side="left", padx=5)

        self.convert_button = tk.Button(
            row6, text="Convert",
            state="disabled",
            command=self.do_convert
        )
        self.convert_button.pack(side="left", padx=15)

    def _build_output_panel(self):

        out_frame = tk.LabelFrame(self, text="Result")
        out_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # ---- Left side: buttons + data text ----
        left_col = tk.Frame(out_frame)
        left_col.pack(side="left", fill="both", expand=True)

        # Buttons
        btn_row = tk.Frame(left_col)
        btn_row.pack(fill="x", padx=5, pady=5)

        self.copy_btn = tk.Button(
            btn_row, text="Copy Data",
            state="disabled",
            command=self._copy_to_clipboard
        )
        self.copy_btn.pack(side="left", padx=5)

        self.save_file_btn = tk.Button(
            btn_row, text="Save as File",
            state="disabled",
            command=self._save_as_file
        )
        self.save_file_btn.pack(side="left", padx=5)

        self.save_img_btn = tk.Button(
            btn_row, text="Save Image",
            state="disabled",
            command=self._save_image
        )
        self.save_img_btn.pack(side="left", padx=5)

        # Data text widget with scrollbars
        text_frame = tk.Frame(left_col)
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        scroll_y = tk.Scrollbar(text_frame, orient="vertical")
        scroll_x = tk.Scrollbar(text_frame, orient="horizontal")
        scroll_y.pack(side="right",  fill="y")
        scroll_x.pack(side="bottom", fill="x")

        self.data_text = tk.Text(
            text_frame,
            state="disabled",
            wrap="none",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            width=60,
            height=20,
        )
        self.data_text.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=self.data_text.yview)
        scroll_x.config(command=self.data_text.xview)

        # ---- Right side: preview pinned to top ----
        right_col = tk.Frame(out_frame)
        right_col.pack(side="right", anchor="n", padx=10, pady=5)

        tk.Label(right_col, text="Converted Preview").pack()

        converted_container = tk.Frame(
            right_col,
            width=self.preview_w,
            height=self.preview_h,
            bg="white",
            relief="solid",
            bd=1
        )
        converted_container.pack()
        converted_container.pack_propagate(False)

        self.converted_preview_label = tk.Label(converted_container, bg="white")
        self.converted_preview_label.place(relx=0.5, rely=0.5, anchor="center")

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

        self._update_preview(self.original_image)
        self.convert_button.config(state="normal")

    def _update_preview(self, pil_image):
        """Resize image to fit preview box and display it."""
        img = pil_image.copy()
        if img.width > self.preview_w or img.height > self.preview_h:
            img.thumbnail((self.preview_w, self.preview_h))
        photo = ImageTk.PhotoImage(img)
        self.preview_label.config(image=photo)
        self.preview_label.image = photo  # prevent garbage collection

    def _copy_to_clipboard(self):
        """Copy generated data to clipboard."""
        if not hasattr(self, "output_text") or not self.output_text:
            return
        self.clipboard_clear()
        self.clipboard_append(self.output_text)
        messagebox.showinfo("Copied", "Data copied to clipboard.")

    # ---------------------------------------------------------
    def _save_as_file(self):
        """Save generated data to a .h / .hpp / .c / .txt file."""
        if not hasattr(self, "output_text") or not self.output_text:
            return

        output_dir = settings.getstr("Paths", "output_dir", fallback=str(os.path.expanduser("~")))
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = str(os.path.expanduser("~"))

        name = self.image_name_var.get().strip() or "my_image"

        file_path = filedialog.asksaveasfilename(
            title="Save Data File",
            initialdir=output_dir,
            initialfile=name,
            defaultextension=".h",
            filetypes=[
                ("Header File",  "*.h"),
                ("C++ Header",   "*.hpp"),
                ("C Source",     "*.c"),
                ("Text File",    "*.txt"),
                ("All Files",    "*.*"),
            ]
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.output_text)
        messagebox.showinfo("Saved", f"Data saved to:\n{file_path}")

    # ---------------------------------------------------------
    def _save_image(self):
        """Save the converted PIL image to file."""
        if not self.core.converted_image:
            return

        output_dir = settings.getstr("Paths", "output_dir", fallback=str(os.path.expanduser("~")))
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = str(os.path.expanduser("~"))

        name = self.image_name_var.get().strip() or "my_image"

        file_path = filedialog.asksaveasfilename(
            title="Save Converted Image",
            initialdir=output_dir,
            initialfile=name,
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("BMP Image", "*.bmp"),
                ("All Files", "*.*"),
            ]
        )
        if not file_path:
            return

        # RGB565 was stored as RGB in PIL — save as-is
        self.core.converted_image.save(file_path)
        messagebox.showinfo("Saved", f"Image saved to:\n{file_path}")

        # ---------------------------------------------------------
    def do_convert(self):
        """Run conversion with current settings and populate output panel."""
        if not self.original_image:
            return

        raw = self.core.convert(
            self.original_image,
            palette_mode = self.palette_var.get(),
            endian       = self.endian_var.get(),
            resize_w     = self.resize_w_var.get(),
            resize_h     = self.resize_h_var.get(),
        )

        self.output_text = self.core.format_bytes(
            raw_bytes = raw,
            opts      = FormatOptions(
                output_format  = self.output_format_var.get(),
                datatype       = self.datatype_var.get(),
                image_name     = self.image_name_var.get().strip() or "my_image",
                multiline      = self.multiline_var.get(),
                separate_bytes = self.separate_bytes_var.get(),
                palette_mode   = self.palette_var.get(),
            )
        )

        # Populate data text widget
        self.data_text.config(state="normal")
        self.data_text.delete("1.0", tk.END)
        self.data_text.insert(tk.END, self.output_text)
        self.data_text.config(state="disabled")

        # Update converted preview
        self._update_converted_preview(self.core.converted_image)

        # Enable output buttons
        self.copy_btn.config(state="normal")
        self.save_file_btn.config(state="normal")
        self.save_img_btn.config(state="normal")

        print(f"Conversion complete: {len(raw)} bytes")

    # ---------------------------------------------------------
    def _update_converted_preview(self, pil_image):
        """Display the converted image in the bottom preview."""
        img = pil_image.copy()
        # Convert to RGB for display if greyscale
        if img.mode == "L":
            img = img.convert("RGB")
        if img.width > self.preview_w or img.height > self.preview_h:
            img.thumbnail((self.preview_w, self.preview_h))
        photo = ImageTk.PhotoImage(img)
        self.converted_preview_label.config(image=photo)
        self.converted_preview_label.image = photo


class ColourBitCore:
    """Handles all image conversion logic for colour images."""

    def __init__(self):
        self.width        = 0
        self.height       = 0
        self.palette_mode = "RGB565"
        self.endian       = "little"
        self.raw_bytes    = []
        self.converted_image = None  # PIL image after palette conversion and resize

    def convert(self, pil_image, palette_mode, endian, resize_w=None, resize_h=None):  # pylint: disable=too-many-arguments
        """
        Main entry point. Takes a PIL image and settings,
        returns a flat list of bytes ready for formatting.
        """
        self.palette_mode = palette_mode
        self.endian       = endian

        # Step 1: resize if requested
        img = self._apply_resize(pil_image, resize_w, resize_h)

        # Step 2: convert to target colour mode
        img = self._apply_palette(img, palette_mode)
        self.converted_image = img
        self.width, self.height = img.size

        # Step 3: pack pixels into bytes
        self.raw_bytes = self._pack_pixels(img, palette_mode, endian)

        return self.raw_bytes
    # ---------------------------------------------------------
    def _apply_resize(self, img, resize_w, resize_h):
        """Resize image, maintaining aspect ratio if only one dimension given."""
        orig_w, orig_h = img.size

        try:
            rw = int(resize_w) if resize_w and str(resize_w).strip() else None
        except ValueError:
            rw = None
        try:
            rh = int(resize_h) if resize_h and str(resize_h).strip() else None
        except ValueError:
            rh = None

        if rw and rh:
            return img.resize((rw, rh), LANCZOS)

        if rw:
            rh = int(orig_h * rw / orig_w)
            return img.resize((rw, rh), LANCZOS)

        if rh:
            rw = int(orig_w * rh / orig_h)
            return img.resize((rw, rh), LANCZOS)

        return img.copy()

    # ---------------------------------------------------------
    def _apply_palette(self, img, palette_mode):
        """Convert PIL image to the target colour mode."""
        if palette_mode == "L":
            # 8-bit greyscale
            return img.convert("L")

        if palette_mode == "RGB":
            # 24-bit RGB
            return img.convert("RGB")

        if palette_mode == "RGBA":
            # 32-bit RGBA — ensure alpha channel exists
            return img.convert("RGBA")

        if palette_mode == "RGB565":
            # PIL has no native RGB565 — convert to RGB first,
            # pixel packing handled in _pack_pixels
            return img.convert("RGB")

        return img.copy()

    # ---------------------------------------------------------
    def _pack_pixels(self, img, palette_mode, endian):
        """Pack image pixels into a flat byte list."""
        raw = []
        pixels = list(img.getdata())

        for pixel in pixels:

            if palette_mode == "L":
                # 8-bit greyscale — 1 byte per pixel
                raw.append(pixel & 0xFF)

            elif palette_mode == "RGB":
                # 24-bit RGB — 3 bytes per pixel
                r, g, b = pixel
                raw.extend([r & 0xFF, g & 0xFF, b & 0xFF])

            elif palette_mode == "RGBA":
                # 32-bit RGBA — 4 bytes per pixel
                r, g, b, a = pixel
                raw.extend([r & 0xFF, g & 0xFF, b & 0xFF, a & 0xFF])

            elif palette_mode == "RGB565":
                # 16-bit RGB565 — pack into 2 bytes
                # Format: RRRRRGGGGGGBBBBB
                r, g, b = pixel
                value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                if endian == "little":
                    raw.append(value & 0xFF)         # low byte first
                    raw.append((value >> 8) & 0xFF)  # high byte second
                else:
                    raw.append((value >> 8) & 0xFF)  # high byte first
                    raw.append(value & 0xFF)          # low byte second

        return raw

    # ---------------------------------------------------------
    def format_bytes(self, raw_bytes, opts: FormatOptions):
        """Format raw bytes into a C array string."""
        bytes_per_pixel = {
            "L":      1,
            "RGB":    3,
            "RGBA":   4,
            "RGB565": 2,
        }.get(opts.palette_mode, 1)

        bytes_per_line = (
            self.width * bytes_per_pixel if opts.multiline
            else len(raw_bytes)
        )

        def fmt(b):
            if opts.output_format == "hex":
                return f"0x{b:02X}"
            if opts.output_format == "decimal":
                return str(b)
            if opts.output_format == "binary":
                return f"0b{b:08b}"
            return str(b)

        formatted = [fmt(b) for b in raw_bytes]
        lines     = []

        if opts.separate_bytes and bytes_per_pixel > 1:
            for i in range(0, len(formatted), bytes_per_line):
                row = formatted[i:i + bytes_per_line]
                pixels_in_row = [
                    ", ".join(row[p:p + bytes_per_pixel])
                    for p in range(0, len(row), bytes_per_pixel)
                ]
                lines.append("    " + ",  ".join(pixels_in_row))
        else:
            for i in range(0, len(formatted), bytes_per_line):
                lines.append("    " + ", ".join(formatted[i:i + bytes_per_line]))

        body = ",\n".join(lines)

        mode_labels = {
            "L":      "8-bit Greyscale",
            "RGB":    "24-bit RGB",
            "RGBA":   "32-bit RGBA",
            "RGB565": "16-bit RGB565",
        }
        guard = f"{opts.image_name.upper()}_H"

        return (
            f"#ifndef {guard}\n"
            f"#define {guard}\n"
            f"\n"
            f"#include <stdint.h>\n"
            f"\n"
            f"// -------------------------------------------------------\n"
            f"// Generated by Guardian LTSM - Colour Bit Converter\n"
            f"// Image Name   : {opts.image_name}\n"
            f"// Dimensions   : {self.width} x {self.height} px\n"
            f"// Colour Mode  : {mode_labels.get(opts.palette_mode, opts.palette_mode)}\n"
            f"// Data Size    : {len(raw_bytes)} bytes\n"
            f"// Endianness   : {self.endian}-endian\n"
            f"// -------------------------------------------------------\n"
            f"\n"
            f"#define {opts.image_name.upper()}_WIDTH   {self.width}\n"
            f"#define {opts.image_name.upper()}_HEIGHT  {self.height}\n"
            f"\n"
            f"const {opts.datatype} {opts.image_name}[] = {{\n"
            f"{body}\n"
            f"}};\n"
            f"\n"
            f"#endif // {guard}\n"
        )

if __name__ == "__main__":
    print("This is a module, not a standalone script.")
else:
    print("Colour bit image convertor module loaded.")
