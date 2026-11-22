import tkinter as tk
import os
import ctypes
from ctypes import wintypes
from screen_io.screen_capture import user32
from dataclasses import dataclass

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

@dataclass
class FocusedWindow:
    hwnd: int
    pid: int
    title: str

def get_focused_details(include_own_windows: bool = False):
    hwnd = user32.GetForegroundWindow()
    if not hwnd or user32.IsIconic(hwnd):
        return None

    pid = _window_pid(hwnd)
    if pid == os.getpid() and not include_own_windows:
        return None

    return FocusedWindow(hwnd=hwnd, pid=pid, title=_window_title(hwnd))

def _window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def _window_title(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


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
