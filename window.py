import ctypes
from abc import ABC, abstractmethod
from ctypes import wintypes
from enum import Enum
import tkinter as tk

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


class WindowPosition(Enum):
    """Where to place a window in the work area.

    Each value is (x, y) as a fraction of the free space:
    0 = left/top edge, 0.5 = centered, 1 = right/bottom edge.
    """
    TOP_LEFT = (0.0, 0.0)
    TOP = (0.5, 0.0)
    TOP_RIGHT = (1.0, 0.0)
    UPPER_CENTER = (0.5, 0.25)   # halfway between the top and the center
    LEFT = (0.0, 0.5)
    CENTER = (0.5, 0.5)
    RIGHT = (1.0, 0.5)
    LOWER_CENTER = (0.5, 0.75)   # halfway between the center and the bottom
    BOTTOM_LEFT = (0.0, 1.0)
    BOTTOM = (0.5, 1.0)
    BOTTOM_RIGHT = (1.0, 1.0)


class Window(ABC):
    def __init__(self):
        self.root = self.create_root()
        self.root.update_idletasks()  # lay out widgets so their size is known

    @abstractmethod
    def create_root(self) -> tk.Tk:
        """Create and configure the Tk root for this window."""

    def place_window_at(self, position: WindowPosition, margin: int = MARGIN):
        """Size the window to width x height and move it to `position` on screen."""
        width  = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()

        self.root.geometry(f"{width}x{height}")
        self.root.update_idletasks()  # creates the window frame so we can measure it

        # geometry() sizes the inside of the window, but positions its outer frame,
        # so account for the borders and title bar (both 0 with overrideredirect).
        border = self.root.winfo_rootx() - self.root.winfo_x()
        title_bar = self.root.winfo_rooty() - self.root.winfo_y()
        outer_w = width + 2 * border
        outer_h = height + title_bar + border

        # Free space the window's top-left corner can move within, keeping `margin` from every edge.
        left, top, right, bottom = get_work_area(self.root)
        free_w = max(0, (right - left) - outer_w - 2 * margin)
        free_h = max(0, (bottom - top) - outer_h - 2 * margin)

        fx, fy = position.value
        x = left + margin + round(free_w * fx)
        y = top + margin + round(free_h * fy)
        self.root.geometry(f"{width}x{height}+{x}+{y}")