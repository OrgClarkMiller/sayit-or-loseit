import threading
import tkinter as tk
from window import Window, WindowPosition

POLL_MS = 100

class OverlayWindow(Window):
    def __init__(self):
        self._close_event = threading.Event()
        super().__init__()
        self.render()
        self.place_window_at(WindowPosition.LOWER_CENTER)
        # Check every POLL_MS if the window should be closed
        self.root.after(POLL_MS, self._check_close)
        self.root.mainloop()

    def create_root(self):
        root = tk.Tk()
        root.title("Say it or Lose it — Configuration")
        root.resizable(False, False)
        root.geometry("400x400")

        # Hide toolbar
        root.overrideredirect(True)

        # Make transparent
        root.config(bg="magenta")
        root.attributes("-transparentcolor", "magenta")
        root.attributes("-topmost", True)  # usually wanted for an overlay
        return root

    def render(self):
        tk.Label(self.root, text="Configuration", font=("Segoe UI", 12, "bold"),
             bg="magenta", fg="white") \
        .pack()

    def close(self):
        self._close_event.set()

    def _check_close(self):
        # Runs on the Tk thread, so destroying here is safe.
        if self._close_event.is_set():
            self.root.destroy()
        else:
            self.root.after(POLL_MS, self._check_close)