import base64
import io
import time
from pathlib import Path
import tkinter as tk
from typing import TYPE_CHECKING
import color_palette  # project root module, not part of the window package
from icons import Icon, GifIcon

from PIL import Image, ImageSequence
from .window import MARGIN, Window, WindowPosition
from screen_io.screen_capture import exclude_from_capture, user32
from .window_helpers import app_window_below, hwnd, is_app_window, make_click_through, round_corners
from punishment.fail_severity import FailSeverity, get_fail_severity, FAIL_SEVERITY_COLOR

if TYPE_CHECKING:  # forward ref: app_context imports this module, so a real import would be circular
    from app_context import AppContext

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
PROCESSING_HIDE_GRACE_MS = 400  # how long the spinner lingers in case another loading step follows
PUNISHMENT_MIN_SHOW_MS = 2500   # instant punishments (a tab closing) still get read before the round's content returns


mic_icon         = Icon("microphone-icon.png", 16)
loading_gif_icon = GifIcon("loading.gif", 24, 100)  # any smaller and the 12 spokes blur together

MIC_IDLE_COLOR = (239, 68, 68)       # red: not recording
MIC_RECORDING_COLOR = (34, 197, 94)  # green: recording

def _tinted_frames(master, path: Path, size: int, color: tuple[int, int, int] | None = None) -> list[tk.PhotoImage]:
    """Every frame of an image (one for a PNG, several for a GIF), shrunk. With a color,
    every visible pixel is filled with it; without, the image keeps its own colors.

    Alpha is snapped to fully opaque or fully transparent: the overlay keys out one exact
    color, so half-transparent edge pixels would be blended with it and show a fringe.
    """
    frames = []
    for frame in ImageSequence.Iterator(Image.open(path)):
        icon = frame.convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = icon.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
        tinted = Image.new("RGBA", icon.size, (*TRANSPARENT_RGB, 255))  # see-through
        fill = icon if color is None else Image.new("RGBA", icon.size, (*color, 255))
        tinted.paste(fill, mask=mask)

        buf = io.BytesIO()
        tinted.save(buf, format="PNG")
        # A plain tk.PhotoImage (not ImageTk) so Window._release_tk frees it on the Tk thread
        frames.append(tk.PhotoImage(master=master, data=base64.b64encode(buf.getvalue())))
    return frames

def _tinted_icon(master, color: tuple[int, int, int]) -> tk.PhotoImage:
    """The mic icon, shrunk and filled with one solid color."""
    return _tinted_frames(master, mic_icon.path, mic_icon.size, color)[0]

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

    def __init__(self, app_context: "AppContext", loading_message: str | None = "Loading..."):
        """It opens in the loading state (spinner + loading_message) until something calls
        set_processing(False), e.g. a ProcessingIndicator block ending. Pass
        loading_message=None to open straight to the normal content instead."""
        super().__init__(app_context)
        self._initial_loading_message = loading_message

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

    def set_attempt(self, n: int, max_attempts: int):
        self.call(self._set_attempt, n, max_attempts)

    def set_processing(self, is_processing: bool, message: str = ""):
        """Show only the loading spinner, with an optional message beside it, e.g.
        "Generating sentence...". Everything else comes back when set to False."""
        self.call(self._set_processing, is_processing, message)

    def set_punishment(self, name: str | None = None, severity: FailSeverity | None = None):
        """Show only the punishment being applied, e.g. ("Close Media", SEVERE):

                    PUNISHMENT  ·  SEVERE
                         Close Media

        Pass None to go back to the normal content (after a short minimum display time,
        so instant punishments can still be read). The loading spinner takes priority
        if both are on."""
        self.call(self._set_punishment, name, severity)

    # ---- Tk thread ----

    def build(self):
        # Keep references: Tk drops an image once Python frees it
        self.mic_idle_icon      = _tinted_icon(self.root, MIC_IDLE_COLOR)
        self.mic_recording_icon = _tinted_icon(self.root, MIC_RECORDING_COLOR)
        self.loading_frames     = _tinted_frames(self.root, loading_gif_icon.path, loading_gif_icon.size)  # untinted

        self._recording = False
        self._rec_start = self._rec_end = 0.0
        self._tick_id: str | None = None

        self._processing = False
        self._loading_frame = 0
        self._spin_id: str | None = None
        self._hide_id: str | None = None  # pending end of the loading state (see _set_processing)

        self._punishing = False
        self._punish_shown_at = 0.0
        self._punish_hide_id: str | None = None  # pending end of the punishment state

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

        self.mic_item     = c.create_image(0, 0, image=self.mic_idle_icon, anchor="ne")
        self.loading_item = c.create_image(0, 0, image=self.loading_frames[0], anchor="nw", state="hidden")
        self.rec_dot      = c.create_oval(0, 0, 0, 0, fill=color_palette.RED, outline=color_palette.OUTLINE, state="hidden")
        self.bar_track    = c.create_rectangle(0, 0, 0, 0, fill=color_palette.TRACK, outline=color_palette.OUTLINE, state="hidden")
        self.bar_fill     = c.create_rectangle(0, 0, 0, 0, fill=color_palette.GREEN, width=0, state="hidden")
        if self._initial_loading_message is not None:
            self._set_processing(True, self._initial_loading_message)  # also lays out
        else:
            self._layout()

    def render_headers(self):
        self._add_text("header", HEADER_FONT, color_palette.MUTED)
        self._add_text("attempt", HEADER_FONT, color_palette.MUTED)
        self._add_text("status", STATUS_FONT, color_palette.MUTED)
        self._add_text("sentence", SENTENCE_FONT, color_palette.TEXT, wrap=MAX_TEXT_WIDTH)
        self._add_text("translation", SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)
        self._add_text("processing", SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)
        self._add_text("punish_title", HEADER_FONT, color_palette.RED)
        self._add_text("punish_name", SENTENCE_FONT, color_palette.TEXT, wrap=MAX_TEXT_WIDTH)

    def on_show(self):
        self.place_window_at(WindowPosition.LOWER_CENTER)
        hwnds = [hwnd(self.root), hwnd(self.backdrop)]
        for handle in hwnds:  # not "hwnd": that would shadow the hwnd() helper for the whole method
            make_click_through(handle)
            # Keep the overlay out of our own screen captures (it sits on top of the focused window)
            exclude_from_capture(handle)
        round_corners(hwnds[1])
        self.backdrop.attributes("-alpha", color_palette.BACKDROP_ALPHA)
        # Tk focused the overlay when it appeared: hand focus back, or challenges would
        # screenshot the overlay (which capture skips) instead of the user's app. If the
        # window that had focus is gone or is ours (e.g. the config window, which closes
        # just as challenges get switched on), use the app window under the overlay.
        if user32.GetForegroundWindow() in hwnds:
            target = self._previous_focus if is_app_window(self._previous_focus) else app_window_below(hwnds[0])
            if target:
                user32.SetForegroundWindow(target)

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

    def _set_attempt(self, n: int, max_attempts: int):
        self._set_text("attempt", f"Attempt {n} of {max_attempts}")
        self._layout()

    def _set_processing(self, is_processing: bool, message: str = ""):
        if not is_processing:
            # Don't drop the spinner straight away: one loading step often ends just before
            # the next begins ("Loading Language" -> "Generating Sentence"), and showing the
            # normal content in between flashes it for a frame. If the next step arrives
            # within the grace period, only the message changes.
            if self._processing and self._hide_id is None:
                self._hide_id = self.root.after(PROCESSING_HIDE_GRACE_MS, self._end_processing)
            return

        if self._hide_id is not None:  # a step ended moments ago: carry straight on
            self.root.after_cancel(self._hide_id)
            self._hide_id = None
        self._set_text("processing", message)
        self._apply_processing(True)

    def _end_processing(self):
        self._hide_id = None
        self._set_text("processing", "")
        self._apply_processing(False)

    def _apply_processing(self, is_processing: bool):
        if is_processing == self._processing:
            self._layout()  # only the message changed: re-fit, but don't restart the animation
            return
        self._processing = is_processing
        if self._spin_id is not None:
            self.root.after_cancel(self._spin_id)
            self._spin_id = None

        self.canvas.itemconfigure(self.loading_item, state="normal" if is_processing else "hidden")
        if is_processing:
            self._loading_frame = 0
            self._spin()
        self._layout()  # swaps between the spinner alone and the normal content

    def _set_punishment(self, name: str | None, severity: FailSeverity | None):
        if self._punish_hide_id is not None:  # a new punishment (or clear) replaces the pending hide
            self.root.after_cancel(self._punish_hide_id)
            self._punish_hide_id = None

        if name is None:
            if self._punishing:
                shown_ms = (time.monotonic() - self._punish_shown_at) * 1000
                self._punish_hide_id = self.root.after(max(0, int(PUNISHMENT_MIN_SHOW_MS - shown_ms)), self._end_punishment)
            return

        title = "PUNISHMENT" if severity is None else f"PUNISHMENT  ·  {severity.name}"
        color = color_palette.RED if severity is None else FAIL_SEVERITY_COLOR[severity]
        self._set_text("punish_title", title, color)
        self._set_text("punish_name", name)
        if not self._punishing:
            self._punishing = True
            self._punish_shown_at = time.monotonic()
        self._layout()

    def _end_punishment(self):
        self._punish_hide_id = None
        self._punishing = False
        self._set_text("punish_title", "")
        self._set_text("punish_name", "")
        self._layout()

    def _spin(self):
        """Show the next frame of the loading GIF, then keep going until processing stops."""
        self.canvas.itemconfigure(self.loading_item, image=self.loading_frames[self._loading_frame])
        self._loading_frame = (self._loading_frame + 1) % len(self.loading_frames)
        self._spin_id = self.root.after(loading_gif_icon.frame_duration, self._spin)

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

        # One state shows at a time: the spinner while processing, else the punishment
        # while one is applied, else the round's content. The hidden ones come back
        # unchanged when their turn comes.
        if self._processing:
            visible = {"processing"}
        elif self._punishing:
            visible = {"punish_title", "punish_name"}
        else:
            visible = set(self._texts) - {"processing", "punish_title", "punish_name"}
        for name, items in self._texts.items():
            state = "normal" if name in visible else "hidden"
            for item, _, _ in items:
                c.itemconfigure(item, state=state)
        showing_content = not (self._processing or self._punishing)
        c.itemconfigure(self.mic_item, state="normal" if showing_content else "hidden")
        if not showing_content:
            for item in (self.rec_dot, self.bar_track, self.bar_fill):
                c.itemconfigure(item, state="hidden")

        if self._processing:
            # Spinner with the message to its right, centred together as one group
            icon = loading_gif_icon.size
            msg_w, msg_h = self._text_size("processing")
            group_w = icon + (8 + msg_w if msg_w else 0)
            row_h = max(icon, msg_h)
            width = max(MIN_WIDTH, group_w) + 2 * PAD
            left = (width - group_w) / 2
            mid = PAD + row_h / 2
            c.coords(self.loading_item, left, mid - icon / 2)
            self._place_text("processing", left + icon + 8, mid, "w")
            self._resize_canvas(width, row_h + 2 * PAD)
            return

        if self._punishing:
            # Severity title, then the punishment's name under it, both centred
            title_w, title_h = self._text_size("punish_title")
            name_w, name_h = self._text_size("punish_name")
            width = max(MIN_WIDTH, title_w, name_w) + 2 * PAD
            y = PAD
            self._place_text("punish_title", width / 2, y, "n")
            y += title_h + 4
            self._place_text("punish_name", width / 2, y, "n")
            y += name_h
            self._resize_canvas(width, y + PAD)
            return

        header_w, header_h = self._text_size("header")
        attempt_w, attempt_h = self._text_size("attempt")
        status_w, status_h = self._text_size("status")
        sentence_w, sentence_h = self._text_size("sentence")
        translation_w, translation_h = self._text_size("translation")

        right_w = mic_icon.size + (6 + status_w if status_w else 0) + (12 if self._recording else 0)
        left_w = max(header_w, attempt_w)
        width = max(MIN_WIDTH, left_w + 24 + right_w, sentence_w, translation_w) + 2 * PAD

        # Header row: language label with the attempt count under it on the left;
        # REC dot, mic and status on the right, centred on the pair
        y = PAD
        left_h = header_h + (2 + attempt_h if attempt_h else 0)
        row_h = max(left_h, status_h, mic_icon.size)
        mid = y + row_h / 2
        left_top = mid - left_h / 2
        self._place_text("header", PAD, left_top, "nw")
        self._place_text("attempt", PAD, left_top + header_h + 2, "nw")
        self._place_text("status", width - PAD, mid, "e")
        mic_right = width - PAD - (status_w + 6 if status_w else 0)
        c.coords(self.mic_item, mic_right, mid - mic_icon.size / 2)
        dot_x = mic_right - mic_icon.size - 7
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

        self._resize_canvas(width, y + PAD)

    def _resize_canvas(self, width: float, height: float):
        c = self.canvas
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

# Allows you to create a with block around a long-running operation
#to have the overlay display a loading gif until the operation completes
class ProcessingIndicator:
    def __init__(self, overlay: OverlayWindow | None, message: str = ""):
        self._overlay = overlay
        self._message = message

    def __enter__(self):
        if self._overlay is not None:
            self._overlay.set_processing(True, self._message)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._overlay is not None:
            self._overlay.set_processing(False)
        return False # Don't supress exceptions

# Same idea for punishments: the overlay shows which punishment is being applied
#for as long as the block runs (and a moment after, see PUNISHMENT_MIN_SHOW_MS)
class PunishmentIndicator:
    def __init__(self, overlay: OverlayWindow | None, name: str, severity: FailSeverity | None = None):
        self._overlay = overlay
        self._name = name
        self._severity = severity

    def __enter__(self):
        if self._overlay is not None:
            self._overlay.set_punishment(self._name, self._severity)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._overlay is not None:
            self._overlay.set_punishment(None)
        return False # Don't supress exceptions