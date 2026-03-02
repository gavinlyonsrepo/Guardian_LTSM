"""
Module for converting data to C/C++ bitmap arrays and vice versa."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from guardian_ltsm.settings import settings


class OneBitConvert(tk.Frame):
    """ Page for converting TTF fonts to C/C++ bitmap arrays.
    """
    def __init__(self, parent, controller,data_mode):
        super().__init__(parent)
        self.controller = controller
        if data_mode:
            label = tk.Label(self, text="Data Converter", font=("Arial", 24))
            label.pack(pady=20)
        else:
            label = tk.Label(self, text="Bitmap Converter", font=("Arial", 24))
            label.pack(pady=20)