import base64
import io
from pathlib import Path
import tkinter as tk

from PIL import Image
from window import Window, WindowPosition
from screen_io.screen_capture import exclude_from_capture, user32

# Win32 extended window styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000      # required for WS_EX_TRANSPARENT to pass clicks through
WS_EX_TRANSPARENT = 0x00000020  # mouse input goes to whatever is underneath
WS_EX_TOOLWINDOW = 0x00000080   # keep it out of the taskbar and Alt+Tab
WS_EX_NOACTIVATE = 0x08000000   # never take keyboard focus

MIC_ICON_PATH = Path(__file__).parent / "assets" / "microphone-icon.png"
MIC_ICON_SIZE = 24  # px
MIC_IDLE_COLOR = (239, 68, 68)     # red: not recording
MIC_RECORDING_COLOR = (34, 197, 94)  # green: recording

def _tinted_icon(master, color: tuple[int, int, int]) -> tk.PhotoImage:
    """The mic icon, shrunk and filled with one solid color.

    Alpha is snapped to fully opaque or fully transparent: the overlay keys out magenta,
    so half-transparent edge pixels would be blended with it and show a pink fringe.
    """
    icon = Image.open(MIC_ICON_PATH).convert("RGBA").resize((MIC_ICON_SIZE, MIC_ICON_SIZE), Image.LANCZOS)
    mask = icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    tinted = Image.new("RGBA", icon.size, (255, 0, 255, 255))  # magenta = see-through
    tinted.paste(Image.new("RGBA", icon.size, (*color, 255)), mask=mask)

    buf = io.BytesIO()
    tinted.save(buf, format="PNG")
    # A plain tk.PhotoImage (not ImageTk) so Window._release_tk frees it on the Tk thread
    return tk.PhotoImage(master=master, data=base64.b64encode(buf.getvalue()))

class OverlayWindow(Window):
    """Always-on-top, click-through text overlay.

    Construct it, then start(). Its public methods are safe to call from any thread.
    It closes when the app's stop_event is set.
    """

    # ---- Thread-safe API ----

    def set_sentence(self, text: str):
        self.call(self._set_sentence, text)

    def set_closeness(self, percent: float):
        self.call(self._set_closeness, percent)

    def set_recording(self, recording: bool):
        """Turn the microphone icon green (recording) or red (not recording)."""
        self.call(self._set_recording, recording)

    # ---- Tk thread ----

    def build(self):
        self.sentence        = tk.StringVar(self.root, value="")
        self.closeness       = tk.StringVar(self.root, value="")
        # Keep references: Tk drops an image (and the label goes blank) once Python frees it
        self.mic_idle_icon      = _tinted_icon(self.root, MIC_IDLE_COLOR)
        self.mic_recording_icon = _tinted_icon(self.root, MIC_RECORDING_COLOR)
        self.render()

    def on_show(self):
        self.place_window_at(WindowPosition.LOWER_CENTER)
        self.make_click_through()
        # Keep the overlay out of our own screen captures (it sits on top of the focused window)
        hwnd = user32.GetParent(self.root.winfo_id())
        exclude_from_capture(hwnd)
        if self._previous_focus and user32.GetForegroundWindow() == hwnd:
            user32.SetForegroundWindow(self._previous_focus)

    def _set_sentence(self, text: str):
        self.sentence.set(text)
        self.place_window_at(WindowPosition.LOWER_CENTER)  # re-fit and re-center for the new length

    # TODO: RETURN BG AND FG
    def _calc_closeness_color(self, percent: float) -> str:
        """Text color for a similarity score: red (way off) through to green (spot on)."""
        if percent < 15: return 'red'
        elif percent < 30: return '#f97316'  # orange
        elif percent < 50: return '#facc15'  # yellow
        elif percent < 75: return '#a3e635'  # yellow-green
        else: return '#22c55e'               # green

    def _set_closeness(self, percent: float):
        self.closeness.set(f"{percent:.2f}% Similarity")
        self.closeness_label.config(fg=self._calc_closeness_color(percent))

    def _set_recording(self, recording: bool):
        self.mic_label.config(image=self.mic_recording_icon if recording else self.mic_idle_icon)

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
        # pack() returns None, so create and pack separately to keep the widget references
        self.mic_label = tk.Label(self.root, image=self.mic_idle_icon, bg="magenta")
        self.mic_label.pack()

        self.closeness_label = tk.Label(self.root, textvariable=self.closeness, font=("Segoe UI", 12, "bold"),
            bg="magenta", fg="white")
        self.closeness_label.pack()

        self.sentence_label = tk.Label(self.root, textvariable=self.sentence, font=("Segoe UI", 12, "bold"),
            bg="magenta", fg="white")
        self.sentence_label.pack()

    def make_click_through(self):
        """Let all mouse input pass through the overlay to the windows below (Windows only)."""
        self.root.update_idletasks()  # make sure the native window exists
        # winfo_id() is Tk's inner client window; its parent is the real top-level window.
        hwnd = user32.GetParent(self.root.winfo_id())
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
