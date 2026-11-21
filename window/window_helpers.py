import tkinter as tk
import ctypes
from screen_io.screen_capture import user32

# Win32 extended window styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000      # required for WS_EX_TRANSPARENT to pass clicks through
WS_EX_TRANSPARENT = 0x00000020  # mouse input goes to whatever is underneath
WS_EX_TOOLWINDOW = 0x00000080   # keep it out of the taskbar and Alt+Tab
WS_EX_NOACTIVATE = 0x08000000   # never take keyboard focus

def hwnd(window: tk.Misc) -> int:
    """The real top-level Win32 window of a Tk root or Toplevel."""
    window.update_idletasks()  # make sure the native window exists
    # winfo_id() is Tk's inner client window; its parent is the real top-level window.
    return user32.GetParent(window.winfo_id())


def make_click_through(hwnd: int):
    """Let all mouse input pass through the window to the windows below (Windows only)."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def round_corners(hwnd: int):
    """Ask Windows 11 to round the window's corners. Does nothing on Windows 10."""
    DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
    try:
        pref = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                                                   ctypes.byref(pref), ctypes.sizeof(pref))
    except (AttributeError, OSError):
        pass
