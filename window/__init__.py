"""Tk windows that each run on their own thread. See window.Window for how they work."""
from .window import MARGIN, Window, WindowPosition, get_work_area
from .overlay import OverlayWindow
from .configuration_window import ConfigurationWindow
from .window_helpers import get_focused_details

__all__ = [
    "MARGIN",
    "Window",
    "WindowPosition",
    "get_work_area",
    "OverlayWindow",
    "ConfigurationWindow",
    "get_focused_details"
]
