import tkinter as tk
from window import Window, WindowPosition
from screen_io.screen_capture import exclude_from_capture, user32

# Win32 extended window styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000      # required for WS_EX_TRANSPARENT to pass clicks through
WS_EX_TRANSPARENT = 0x00000020  # mouse input goes to whatever is underneath
WS_EX_TOOLWINDOW = 0x00000080   # keep it out of the taskbar and Alt+Tab
WS_EX_NOACTIVATE = 0x08000000   # never take keyboard focus

class OverlayWindow(Window):
    """Always-on-top, click-through text overlay.

    Construct it, then start(). Its public methods are safe to call from any thread.
    Pass the app's stop_event so it closes when the app does.
    """

    # ---- Thread-safe API ----

    def set_text(self, text: str):
        self.call(self._set_text, text)

    # ---- Tk thread ----

    def build(self):
        self.text = tk.StringVar(self.root, value="")
        self.render()

    def on_show(self):
        self.place_window_at(WindowPosition.LOWER_CENTER)
        self.make_click_through()
        # Keep the overlay out of our own screen captures (it sits on top of the focused window)
        hwnd = user32.GetParent(self.root.winfo_id())
        exclude_from_capture(hwnd)
        if self._previous_focus and user32.GetForegroundWindow() == hwnd:
            user32.SetForegroundWindow(self._previous_focus)

    def _set_text(self, text):
        self.text.set(text)
        self.place_window_at(WindowPosition.LOWER_CENTER)  # re-fit and re-center for the new length

    def create_root(self):
        # Tk activates a window when it first appears, before WS_EX_NOACTIVATE can be set.
        # Remember who had focus so on_show() can hand it back.
        self._previous_focus = user32.GetForegroundWindow()
        root = tk.Tk()
        root.title("Say it or Lose it — Overlay")
        root.resizable(False, False)

        # Hide toolbar
        root.overrideredirect(True)

        # Make transparent
        root.config(bg="magenta")
        root.attributes("-transparentcolor", "magenta")
        root.attributes("-topmost", True)  # usually wanted for an overlay
        return root

    def render(self):
        tk.Label(self.root, textvariable=self.text, font=("Segoe UI", 12, "bold"),
             bg="magenta", fg="white") \
        .pack()

    def make_click_through(self):
        """Let all mouse input pass through the overlay to the windows below (Windows only)."""
        self.root.update_idletasks()  # make sure the native window exists
        # winfo_id() is Tk's inner client window; its parent is the real top-level window.
        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
