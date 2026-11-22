from typing import Callable
import tkinter as tk

import color_palette  # project root module, not part of the window package
from punishment.fail_severity import FAIL_SEVERITY_COLOR, get_fail_severity

from ..outlined_text import OutlinedText
from ..states import ChallengeState
from ..style import (BAR_HEIGHT, HEADER_FONT, MAX_TEXT_WIDTH, MIN_WIDTH, PAD, SENTENCE_FONT,
                     SMALL_FONT, STATUS_FONT, TICK_MS, mic_icon)
from .base import OverlayView


class ContentView(OverlayView[ChallengeState]):
    """The round itself: language and attempt, mic and status, sentence and translation,
    and a countdown bar while recording. See ChallengeState for the picture."""

    def __init__(self, canvas: tk.Canvas, request_layout: Callable[[], None],
                 mic_idle: tk.PhotoImage, mic_recording: tk.PhotoImage):
        super().__init__(canvas, request_layout)
        self._mic_idle = mic_idle
        self._mic_recording = mic_recording
        self._state = ChallengeState()

        self.header      = OutlinedText(canvas, HEADER_FONT, color_palette.MUTED)
        self.attempt     = OutlinedText(canvas, HEADER_FONT, color_palette.MUTED)
        self.status      = OutlinedText(canvas, STATUS_FONT, color_palette.MUTED)
        self.sentence    = OutlinedText(canvas, SENTENCE_FONT, color_palette.TEXT, wrap=MAX_TEXT_WIDTH)
        self.translation = OutlinedText(canvas, SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)
        self._texts = (self.header, self.attempt, self.status, self.sentence, self.translation)

        self.mic       = canvas.create_image(0, 0, image=mic_idle, anchor="ne", state="hidden")
        self.rec_dot   = canvas.create_oval(0, 0, 0, 0, fill=color_palette.RED, outline=color_palette.OUTLINE, state="hidden")
        self.bar_track = canvas.create_rectangle(0, 0, 0, 0, fill=color_palette.TRACK, outline=color_palette.OUTLINE, state="hidden")
        self.bar_fill  = canvas.create_rectangle(0, 0, 0, 0, fill=color_palette.GREEN, width=0, state="hidden")

    def update(self, state: ChallengeState):
        self._state = state
        self.header.set(f"{state.language.upper()}  ·  {state.level}" if state.language else "")
        self.attempt.set(f"Attempt {state.attempt} of {state.max_attempts}" if state.attempt else "")
        self.sentence.set(state.target_sentence)
        self.translation.set(state.source_sentence)
        recording = state.recording is not None
        self.canvas.itemconfigure(self.mic, image=self._mic_recording if recording else self._mic_idle)

        self._stop_timer()
        self._refresh_status()
        if recording and state.recording.seconds_left() > 0:
            self._start_timer(TICK_MS, self._tick)

    def layout(self) -> tuple[float, float]:
        c = self.canvas
        recording = self._state.recording
        header_w, header_h = self.header.size()
        attempt_w, attempt_h = self.attempt.size()
        status_w, status_h = self.status.size()
        sentence_w, sentence_h = self.sentence.size()
        translation_w, translation_h = self.translation.size()

        right_w = mic_icon.size + (6 + status_w if status_w else 0) + (12 if recording else 0)
        left_w = max(header_w, attempt_w)
        width = max(MIN_WIDTH, left_w + 24 + right_w, sentence_w, translation_w) + 2 * PAD

        # Header row: language label with the attempt count under it on the left;
        # REC dot, mic and status on the right, centred on the pair
        y = PAD
        left_h = header_h + (2 + attempt_h if attempt_h else 0)
        row_h = max(left_h, status_h, mic_icon.size)
        mid = y + row_h / 2
        left_top = mid - left_h / 2
        self.header.place(PAD, left_top, "nw")
        self.attempt.place(PAD, left_top + header_h + 2, "nw")
        self.status.place(width - PAD, mid, "e")
        mic_right = width - PAD - (status_w + 6 if status_w else 0)
        c.coords(self.mic, mic_right, mid - mic_icon.size / 2)
        dot_x = mic_right - mic_icon.size - 7
        c.coords(self.rec_dot, dot_x - 3.5, mid - 3.5, dot_x + 3.5, mid + 3.5)
        c.itemconfigure(self.rec_dot, state="normal" if recording else "hidden")
        y += row_h + 10

        # Sentence, then the translation under it
        if sentence_h:
            self.sentence.place(width / 2, y, "n")
            y += sentence_h + 2
        if translation_h:
            self.translation.place(width / 2, y, "n")
            y += translation_h

        # Countdown bar, only while recording with a known duration
        show_bar = recording is not None and recording.has_countdown
        if show_bar:
            y += 10
            frac = recording.fraction_left()
            c.coords(self.bar_track, PAD, y, width - PAD, y + BAR_HEIGHT)
            c.coords(self.bar_fill, PAD + 1, y + 1, PAD + 1 + (width - 2 * PAD - 2) * frac, y + BAR_HEIGHT)
            y += BAR_HEIGHT
        for item in (self.bar_track, self.bar_fill):
            c.itemconfigure(item, state="normal" if show_bar else "hidden")

        return width, y + PAD

    def _set_visible(self, visible: bool):
        for text in self._texts:
            text.set_visible(visible)
        self.canvas.itemconfigure(self.mic, state="normal" if visible else "hidden")
        if not visible:  # when visible, layout() decides on these
            for item in (self.rec_dot, self.bar_track, self.bar_fill):
                self.canvas.itemconfigure(item, state="hidden")

    def _refresh_status(self):
        """REC countdown while recording, else the score, else nothing."""
        recording = self._state.recording
        percent = self._state.similarity_percent
        if recording is not None:
            text = f"REC  {recording.seconds_left():.0f}s" if recording.has_countdown else "REC"
            self.status.set(text, color_palette.GREEN)
        elif percent is not None:
            self.status.set(f"{percent:.0f}%", FAIL_SEVERITY_COLOR[get_fail_severity(percent)])
        else:
            self.status.set("")

    def _tick(self):
        """Redraw the countdown while recording."""
        self._refresh_status()
        self.request_layout()
        if self._state.recording is not None and self._state.recording.seconds_left() > 0:
            self._start_timer(TICK_MS, self._tick)
        else:
            self._timer_id = None
