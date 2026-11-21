"""Capture what the focused window is showing (Windows only)."""
import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

from PIL import Image, ImageGrab

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

user32.GetForegroundWindow.restype = wintypes.HWND  # avoid truncating the handle on 64-bit
user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]

DWMWA_EXTENDED_FRAME_BOUNDS = 9
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)


@dataclass
class WindowCapture:
    hwnd: int
    pid: int
    title: str
    bbox: tuple[int, int, int, int]  # (left, top, right, bottom) in physical screen pixels
    image: Image.Image


def capture_focused_window(include_own_windows: bool = False) -> WindowCapture | None:
    """Screenshot of the window that currently has focus.

    Returns None when there's nothing sensible to capture: no focused window (focus is
    switching), it's minimized or has no area, or it belongs to this app (unless
    include_own_windows is True).

    Captures the window's region of the screen rather than asking the window to draw
    itself: GPU-rendered apps (browsers, VS Code, games) come back black otherwise.
    So anything on top of the window is captured too, except windows that opt out
    with exclude_from_capture() (the overlay does).
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd or user32.IsIconic(hwnd):
        return None

    pid = _window_pid(hwnd)
    if pid == os.getpid() and not include_own_windows:
        return None

    bbox = _window_bounds(hwnd)
    left, top, right, bottom = bbox
    if right <= left or bottom <= top:
        return None

    image = ImageGrab.grab(bbox=bbox, all_screens=True)  # all_screens: window may be on any monitor
    return WindowCapture(hwnd=hwnd, pid=pid, title=_window_title(hwnd), bbox=bbox, image=image)


def exclude_from_capture(hwnd: int) -> bool:
    """Hide a top-level window from screenshots and screen capture (it stays visible on
    screen). Needs Windows 10 2004+. Returns False if it isn't supported."""
    WDA_EXCLUDEFROMCAPTURE = 0x11
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))


def _window_bounds(hwnd) -> tuple[int, int, int, int]:
    """The window's visible frame in physical pixels.

    GetWindowRect includes invisible resize borders, and in a DPI-unaware process it's
    scaled to logical pixels, which wouldn't match the physical pixels ImageGrab
    captures at display scaling above 100%. So query DWM's frame bounds with this
    thread temporarily per-monitor DPI aware.
    """
    rect = wintypes.RECT()
    previous = user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    try:
        failed = dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
        if failed:  # non-zero HRESULT, e.g. DWM unavailable
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
    finally:
        if previous:
            user32.SetThreadDpiAwarenessContext(previous)
    return rect.left, rect.top, rect.right, rect.bottom


def _window_pid(hwnd) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _window_title(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value
