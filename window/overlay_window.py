import base64
import io
import time
from pathlib import Path
import tkinter as tk
import color_palette  # project root module, not part of the window package

from PIL import Image
from .window import MARGIN, Window, WindowPosition
from screen_io.screen_capture import exclude_from_capture, user32
from .window_helpers import hwnd, make_click_through, round_corners
from punishment.fail_severity import get_fail_severity, FAIL_SEVERITY_COLOR

# Keyed out by the window: anything exactly this color is see-through. Near-black rather
# than magenta because Windows anti-aliases text against the background color, so text
# edges get blended with it: near-black blends into the dark outline, magenta leaves pink
# and blue fringes. Nothing else may use this exact color.
TRANSPARENT = "#010101"
TRANSPARENT_RGB = (1, 1, 1)

# Font tuples, not tkinter.font.Font objects: those would be freed on whatever thread
# drops them last, which Tk doesn't allow (see Window._release_tk)
HEADER_FONT   = ("Segoe UI Semibold", 9)
STATUS_FONT   = ("Segoe UI Semibold", 9)
SENTENCE_FONT = ("Segoe UI Semibold", 15)
SMALL_FONT    = ("Segoe UI", 10)

PAD = 12              # px around the content
MIN_WIDTH = 300       # px, so short sentences don't make a tiny, jumpy overlay
MAX_TEXT_WIDTH = 460  # px, longer sentences wrap
BAR_HEIGHT = 4        # px
TICK_MS = 200         # how often the countdown redraws

MIC_ICON_PATH = Path(__file__).parent.parent / "assets" / "microphone-icon.png"  # window/ -> project root
MIC_ICON_SIZE = 16  # px
MIC_IDLE_COLOR = (239, 68, 68)       # red: not recording
MIC_RECORDING_COLOR = (34, 197, 94)  # green: recording


def _tinted_icon(master, color: tuple[int, int, int]) -> tk.PhotoImage:
    """The mic icon, shrunk and filled with one solid color.

    Alpha is snapped to fully opaque or fully transparent: the overlay keys out one exact
    color, so half-transparent edge pixels would be blended with it and show a fringe.
    """
    icon = Image.open(MIC_ICON_PATH).convert("RGBA").resize((MIC_ICON_SIZE, MIC_ICON_SIZE), Image.LANCZOS)
    mask = icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    tinted = Image.new("RGBA", icon.size, (*TRANSPARENT_RGB, 255))  # see-through
    tinted.paste(Image.new("RGBA", icon.size, (*color, 255)), mask=mask)

    buf = io.BytesIO()
    tinted.save(buf, format="PNG")
    # A plain tk.PhotoImage (not ImageTk) so Window._release_tk frees it on the Tk thread
    return tk.PhotoImage(master=master, data=base64.b64encode(buf.getvalue()))

class OverlayWindow(Window):
    """Always-on-top, click-through overlay on a see-through background.

        FRENCH · A2                        ● 🎤 REC 4s
               Le chat dort sur le canapé rouge.
                 the cat sleeps on the red sofa
        ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬────────────────────────   (while recording)

    Everything is drawn on one canvas so text can get a dark outline: with no card behind
    it, that's what keeps it readable over both light and dark windows.

    Construct it, then start(). Its public methods are safe to call from any thread.
    It closes when the app's stop_event is set.
    """

    # ---- Thread-safe API ----

    def set_language_label(self, language: str, level: str):
        """The small header, e.g. ("French", "A2") -> FRENCH · A2"""
        self.call(self._set_language_label, language, level)

    def set_target_lang_sentence(self, text: str):
        """The sentence to say. Also clears the previous round's score."""
        self.call(self._set_target_lang_sentence, text)

    def set_source_lang_sentence(self, text: str):
        """The translation shown under the sentence."""
        self.call(self._set_source_lang_sentence, text)

    def set_similarity_percent(self, percent: float):
        self.call(self._set_similarity_percent, percent)

    def set_recording(self, recording: bool, duration: float | None = None):
        """Turn the mic green (recording) or red (not). With a duration in seconds,
        also show a bar counting down the time left to speak."""
        self.call(self._set_recording, recording, duration)

    # ---- Tk thread ----

    def build(self):
        # Keep references: Tk drops an image once Python frees it
        self.mic_idle_icon      = _tinted_icon(self.root, MIC_IDLE_COLOR)
        self.mic_recording_icon = _tinted_icon(self.root, MIC_RECORDING_COLOR)

        self._recording = False
        self._rec_start = self._rec_end = 0.0
        self._tick_id: str | None = None

        # Translucent dark panel behind the text. A window can either key out one color
        # fully (the text window does that) or fade as a whole (which would fade the text
        # too), so the panel is its own faded window that follows the text window around.
        self.backdrop = tk.Toplevel(self.root, bg=color_palette.BACKDROP)
        self.backdrop.overrideredirect(True)
        self.backdrop.attributes("-topmost", True)
        self.backdrop.attributes("-alpha", 0.0)  # hidden until on_show() has positioned it

        self.render()

    def render(self):
        c = self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        c.pack()

        self._texts: dict[str, list[tuple[int, int, int]]] = {}  # name -> [(item, dx, dy)]
        self.render_headers()

        self.mic_item = c.create_image(0, 0, image=self.mic_idle_icon, anchor="ne")
        self.rec_dot = c.create_oval(0, 0, 0, 0, fill=color_palette.RED, outline=color_palette.OUTLINE, state="hidden")
        self.bar_track = c.create_rectangle(0, 0, 0, 0, fill=color_palette.TRACK, outline=color_palette.OUTLINE, state="hidden")
        self.bar_fill = c.create_rectangle(0, 0, 0, 0, fill=color_palette.GREEN, width=0, state="hidden")
        self._layout()

    def render_headers(self):
        self._add_text("header", HEADER_FONT, color_palette.MUTED)
        self._add_text("status", STATUS_FONT, color_palette.MUTED)
        self._add_text("sentence", SENTENCE_FONT, color_palette.TEXT, wrap=MAX_TEXT_WIDTH)
        self._add_text("translation", SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)

    def on_show(self):
        self.place_window_at(WindowPosition.LOWER_CENTER)
        hwnds = [hwnd(self.root), hwnd(self.backdrop)]
        for handle in hwnds:  # not "hwnd": that would shadow the hwnd() helper for the whole method
            make_click_through(handle)
            # Keep the overlay out of our own screen captures (it sits on top of the focused window)
            exclude_from_capture(handle)
        round_corners(hwnds[1])
        self.backdrop.attributes("-alpha", color_palette.BACKDROP_ALPHA)
        if self._previous_focus and user32.GetForegroundWindow() in hwnds:
            user32.SetForegroundWindow(self._previous_focus)

    def place_window_at(self, position: WindowPosition, margin: int = MARGIN):
        super().place_window_at(position, margin)
        # Keep the panel exactly behind the text window
        self.root.update_idletasks()
        self.backdrop.geometry(f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                               f"+{self.root.winfo_x()}+{self.root.winfo_y()}")
        self.root.lift()  # text above the panel

    def _set_language_label(self, language: str, level: str):
        self._set_text("header", f"{language.upper()}  ·  {level}")
        self._layout()

    def _set_target_lang_sentence(self, text: str):
        self._set_text("sentence", text)
        self._set_text("status", "")  # a new round: the old score no longer applies
        self._layout()

    def _set_source_lang_sentence(self, text: str):
        self._set_text("translation", text)
        self._layout()

    def _set_similarity_percent(self, percent: float):
        fail_sev = get_fail_severity(percent)
        self._set_text("status", f"{percent:.0f}%", FAIL_SEVERITY_COLOR[fail_sev])
        self._layout()

    def _set_recording(self, recording: bool, duration: float | None):
        self._recording = recording
        self.canvas.itemconfigure(self.mic_item, image=self.mic_recording_icon if recording else self.mic_idle_icon)
        if self._tick_id is not None:
            self.root.after_cancel(self._tick_id)
            self._tick_id = None

        if recording:
            self._rec_start = time.monotonic()
            self._rec_end = self._rec_start + (duration or 0)
            self._tick()  # sets the status text and the bar, then keeps itself going
        else:
            self._set_text("status", "")
            self._layout()

    def _tick(self):
        """Redraw the countdown while recording."""
        left = max(0.0, self._rec_end - time.monotonic())
        self._set_text("status", f"REC  {left:.0f}s" if self._rec_end > self._rec_start else "REC", color_palette.GREEN)
        self._layout()
        if left > 0:
            self._tick_id = self.root.after(TICK_MS, self._tick)
        else:
            self._tick_id = None

    # ---- Drawing ----

    def _add_text(self, name: str, font: tuple, color: str, wrap: int = 0):
        """A canvas text with a 1 px dark outline: 8 dark copies around one colored copy."""
        items = []
        for dx, dy in [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1), (0, 0)]:
            fill = color if (dx, dy) == (0, 0) else color_palette.OUTLINE
            item = self.canvas.create_text(0, 0, text="", font=font, fill=fill, width=wrap, justify="center")
            items.append((item, dx, dy))
        self._texts[name] = items

    def _set_text(self, name: str, text: str, color: str | None = None):
        for item, dx, dy in self._texts[name]:
            self.canvas.itemconfigure(item, text=text)
        if color is not None:
            self.canvas.itemconfigure(self._texts[name][-1][0], fill=color)  # the (0, 0) copy

    def _text_size(self, name: str) -> tuple[int, int]:
        item = self._texts[name][-1][0]
        if not self.canvas.itemcget(item, "text"):
            return 0, 0
        x1, y1, x2, y2 = self.canvas.bbox(item)
        return x2 - x1, y2 - y1

    def _place_text(self, name: str, x: float, y: float, anchor: str):
        for item, dx, dy in self._texts[name]:
            self.canvas.coords(item, x + dx, y + dy)
            self.canvas.itemconfigure(item, anchor=anchor)

    def _layout(self):
        """Position everything for the current content, then re-fit the window around it."""
        c = self.canvas
        header_w, header_h = self._text_size("header")
        status_w, status_h = self._text_size("status")
        sentence_w, sentence_h = self._text_size("sentence")
        translation_w, translation_h = self._text_size("translation")

        right_w = MIC_ICON_SIZE + (6 + status_w if status_w else 0) + (12 if self._recording else 0)
        width = max(MIN_WIDTH, header_w + 24 + right_w, sentence_w, translation_w) + 2 * PAD

        # Header row: language label on the left; REC dot, mic and status on the right
        y = PAD
        row_h = max(header_h, status_h, MIC_ICON_SIZE)
        mid = y + row_h / 2
        self._place_text("header", PAD, mid, "w")
        self._place_text("status", width - PAD, mid, "e")
        mic_right = width - PAD - (status_w + 6 if status_w else 0)
        c.coords(self.mic_item, mic_right, mid - MIC_ICON_SIZE / 2)
        dot_x = mic_right - MIC_ICON_SIZE - 7
        c.coords(self.rec_dot, dot_x - 3.5, mid - 3.5, dot_x + 3.5, mid + 3.5)
        c.itemconfigure(self.rec_dot, state="normal" if self._recording else "hidden")
        y += row_h + 10

        # Sentence, then the translation under it
        if sentence_h:
            self._place_text("sentence", width / 2, y, "n")
            y += sentence_h + 2
        if translation_h:
            self._place_text("translation", width / 2, y, "n")
            y += translation_h

        # Countdown bar, only while recording with a known duration
        show_bar = self._recording and self._rec_end > self._rec_start
        if show_bar:
            y += 10
            total = self._rec_end - self._rec_start
            frac = max(0.0, self._rec_end - time.monotonic()) / total
            c.coords(self.bar_track, PAD, y, width - PAD, y + BAR_HEIGHT)
            c.coords(self.bar_fill, PAD + 1, y + 1, PAD + 1 + (width - 2 * PAD - 2) * frac, y + BAR_HEIGHT)
            y += BAR_HEIGHT
        for item in (self.bar_track, self.bar_fill):
            c.itemconfigure(item, state="normal" if show_bar else "hidden")

        height = y + PAD
        if (int(c.cget("width")), int(c.cget("height"))) != (int(width), int(height)):
            c.config(width=width, height=height)
            self.place_window_at(WindowPosition.LOWER_CENTER)  # re-fit and re-center

    # ---- Window setup ----

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
        root.config(bg=TRANSPARENT)
        root.attributes("-transparentcolor", TRANSPARENT)
        root.attributes("-topmost", True)  # usually wanted for an overlay
        return root
