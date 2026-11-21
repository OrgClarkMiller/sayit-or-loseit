import ctypes
import gc
import queue
import threading
import traceback
from abc import ABC, abstractmethod
from ctypes import wintypes
from enum import Enum
from typing import TYPE_CHECKING
import tkinter as tk

# Forward ref for app context: app_context imports the windows, so importing it for real
# here would be circular. Type checkers see it; at runtime the annotation stays a string.
if TYPE_CHECKING:
    from app_context import AppContext

MARGIN = 8  # gap between the window and the screen edge / taskbar
POLL_MS = 50  # how often the Tk thread checks for queued calls and close requests

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
    """A Tk window that runs on its own thread and can be driven from any thread.

    Tk is not thread-safe: the root must be created, used and run on one thread.
    So constructing a Window creates nothing Tk-related; start() spawns the window's
    thread, which builds and shows it. Other threads talk to it through call() and
    close(), which queue work for the Tk thread to run on its next poll.

    Subclasses implement create_root() and build(), and may override on_show()
    and on_close(). Everything except call()/close()/start()/join()/is_alive()
    runs on the Tk thread.
    """

    def __init__(self, app_context: "AppContext"):
        self.root: tk.Tk | None = None
        self._app_context       = app_context       # the window also closes when its stop_event is set
        self._close_event       = threading.Event()
        self._calls             = queue.Queue()
        self._thread: threading.Thread | None = None

    # ---- Thread-safe API: call these from any thread ----

    def start(self):
        """Open the window on its own thread. Returns immediately."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def call(self, func, *args, **kwargs):
        """Run func(*args, **kwargs) on the Tk thread. Calls made before the window
        is up are queued and run once it's built."""
        self._calls.put((func, args, kwargs))

    def close(self):
        """Ask the window to close."""
        self._close_event.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    # ---- Subclass hooks: run on the Tk thread ----

    @abstractmethod
    def create_root(self) -> tk.Tk:
        """Create and configure the Tk root for this window."""

    @abstractmethod
    def build(self):
        """Create the window's widgets and Tk variables."""

    def on_show(self):
        """Runs after build(), just before the window appears (e.g. positioning)."""

    def on_close(self):
        """Runs when the window is asked to close. Override to save state first."""
        self.root.destroy()

    # ---- Internals ----

    def _should_close(self):
        return self._close_event.is_set() or self._app_context.stop_event.is_set()

    def _run(self):
        try:
            self.root = self.create_root()
            # Invisible (not withdrawn) while building: Windows reports bogus frame sizes
            # for withdrawn windows, which would throw off place_window_at().
            self.root.attributes("-alpha", 0.0)
            self.build()
            # Map the window before positioning it. Setting the position of a not-yet-mapped
            # window can lose to Windows' default "cascade" placement when another Tk
            # window is running on a different thread.
            self.root.update()
            self.on_show()
            self.root.attributes("-alpha", 1.0)
            self.root.after(POLL_MS, self._poll)
            self.root.mainloop()
        finally:
            self._release_tk()

    def _release_tk(self):
        """Drop every Tk object on this thread. If the last reference went away on another
        thread (e.g. at interpreter exit), Tk would raise 'main thread is not in main loop'
        or abort with Tcl_AsyncDelete."""
        for name, value in list(vars(self).items()):
            if isinstance(value, (tk.Variable, tk.Misc, tk.Image)):
                setattr(self, name, None)
        gc.collect()  # widgets hold reference cycles; free them here, not on some other thread

    def _poll(self):
        while True:
            try:
                func, args, kwargs = self._calls.get_nowait()
            except queue.Empty:
                break
            try:
                func(*args, **kwargs)
            except Exception:
                traceback.print_exc()  # one bad call shouldn't kill the window

        if self._should_close():
            self.on_close()
        else:
            self.root.after(POLL_MS, self._poll)

    def place_window_at(self, position: WindowPosition, margin: int = MARGIN):
        """Size the window to fit its content and move it to `position` on screen."""
        self.root.update_idletasks()  # lay out widgets so their size is known
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