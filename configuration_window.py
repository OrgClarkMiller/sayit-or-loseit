import ctypes
import tkinter as tk
from ctypes import wintypes

WIDTH, HEIGHT = 500, 300
MARGIN = 8  # gap between the window and the screen edge / taskbar

def get_work_area(root):
    """Screen area excluding the taskbar, as (left, top, right, bottom)."""
    try:
        rect = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom
    except AttributeError:  # not on Windows
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()

class ConfigurationWindow:
    def __init__(self):
        self.root = self.create_root()

        self.render()
        self.place_bottom_right()
        self.root.mainloop()

    def place_bottom_right(self):
        self.root.geometry(f"{WIDTH}x{HEIGHT}")
        self.root.update_idletasks()  # creates the window frame so we can measure it

        # geometry() sizes the inside of the window, but positions its outer frame,
        # so account for the borders and title bar.
        border = self.root.winfo_rootx() - self.root.winfo_x()
        title_bar = self.root.winfo_rooty() - self.root.winfo_y()
        outer_w = WIDTH + 2 * border
        outer_h = HEIGHT + title_bar + border

        _, _, right, bottom = get_work_area(self.root)
        x = right - outer_w - MARGIN
        y = bottom - outer_h - MARGIN
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def create_root(self):
        root = tk.Tk()
        root.title("Say it or Lose it — Configuration")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_destroy)

        return root

    def render(self):
        label = tk.Label(self.root, text="Configuration")
        label.pack()

    def on_begin(self):
       pass

    def on_destroy(self):
        print("Closing Config Window")
        self.root.destroy()  # required: overriding WM_DELETE_WINDOW disables the default close