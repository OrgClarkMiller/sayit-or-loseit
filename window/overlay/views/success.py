import random
import time
from typing import Callable
import tkinter as tk

import color_palette  # project root module, not part of the window package
from punishment.fail_severity import FAIL_SEVERITY_COLOR, FailSeverity, get_fail_severity

from ..outlined_text import OutlinedText
from ..states import SUCCESS_MIN_SHOW_MS, SuccessState
from ..style import (BAR_HEIGHT, HEADER_FONT, MAX_TEXT_WIDTH, MIN_WIDTH, PAD, SENTENCE_FONT,
                     SMALL_FONT, STATUS_FONT, TITLE_FONT, mic_icon)
from .base import OverlayView

# Passing scores only: a perfect one gets a cheer, a close one a nod
MESSAGES = {
    FailSeverity.PERFECT: ["Nailed it!", "Spot on!", "Perfect!", "Flawless!", "Well said!", "Exactly right!"],
    FailSeverity.CLOSE:   ["Close enough!", "Almost there!", "Not bad!", "Nearly perfect!", "Good effort!"],
}
FOOTER = "No punishment  ·  next round"

BADGE = 18          # px, the check circle's diameter
BADGE_GAP = 7       # px between the badge and the title
UNDERLINE = 2       # px, thickness of each word's underline
BAR_MIN_WIDTH = 80  # px, so the footer bar never gets squeezed to nothing
FRAME_MS = 50       # how often the footer bar redraws


class SuccessView(OverlayView[SuccessState]):
    """The sentence said well enough to pass: a check, a random message, the sentence with
    every word underlined, and a bar that fills until the next round can take over.
    See SuccessState for the picture.

    Coloured by the score's severity, like everywhere else: green with a cheer for
    PERFECT, lime with a softer message for CLOSE."""

    def __init__(self, canvas: tk.Canvas, request_layout: Callable[[], None], mic_recording: tk.PhotoImage):
        super().__init__(canvas, request_layout)
        self._visible = False
        self._shown_at = 0.0
        self._state: SuccessState | None = None
        self._message = ""

        self.header      = OutlinedText(canvas, HEADER_FONT, color_palette.MUTED)
        self.score       = OutlinedText(canvas, STATUS_FONT, color_palette.GREEN)
        self.title       = OutlinedText(canvas, TITLE_FONT, color_palette.GREEN)
        self.translation = OutlinedText(canvas, SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)
        self.footer      = OutlinedText(canvas, HEADER_FONT, color_palette.TEXT)
        self.footer.set(FOOTER)
        self._texts = [self.header, self.score, self.title, self.translation, self.footer]

        self.mic       = canvas.create_image(0, 0, image=mic_recording, anchor="ne", state="hidden")  # green
        self.badge     = canvas.create_oval(0, 0, 0, 0, fill=color_palette.GREEN, outline=color_palette.OUTLINE, state="hidden")
        self.tick      = canvas.create_line(0, 0, 0, 0, fill=color_palette.OUTLINE, width=2.5,
                                            capstyle="round", joinstyle="round", state="hidden")
        self.bar_track = canvas.create_rectangle(0, 0, 0, 0, fill=color_palette.TRACK, outline=color_palette.OUTLINE, state="hidden")
        self.bar_fill  = canvas.create_rectangle(0, 0, 0, 0, fill=color_palette.GREEN, width=0, state="hidden")
        self._shapes = [self.mic, self.badge, self.tick, self.bar_track, self.bar_fill]
        self._bar: tuple[float, float, float] = (0, 0, 0)  # left, top, width of the bar's inside

        # One text per word, so each can be underlined; rebuilt for each sentence
        self._words: list[OutlinedText] = []
        self._underlines: list[int] = []
        self._space = self._measure_space()

    def update(self, state: SuccessState):
        severity = get_fail_severity(state.similarity)
        color = FAIL_SEVERITY_COLOR[severity]
        if state is not self._state:  # same object again (e.g. re-rendered): keep its message
            # A failing score shouldn't get here; if it does, it gets the soft message
            self._message = random.choice(MESSAGES.get(severity, MESSAGES[FailSeverity.CLOSE]))
            self._shown_at = time.monotonic()
        if self._state is None or state.target_sentence != self._state.target_sentence:
            self._build_words(state.target_sentence)
        self._state = state

        self.header.set(f"{state.language.upper()}  ·  {state.level}" if state.language else "")
        self.score.set(f"{state.similarity:.0f}%", color)
        self.title.set(self._message, color)
        self.translation.set(state.source_sentence)
        for item in (self.badge, self.bar_fill, *self._underlines):
            self.canvas.itemconfigure(item, fill=color)

        self._stop_timer()
        self._start_timer(FRAME_MS, self._advance_bar)

    def layout(self) -> tuple[float, float]:
        c = self.canvas
        header_w, header_h = self.header.size()
        score_w, score_h = self.score.size()
        title_w, title_h = self.title.size()
        translation_w, translation_h = self.translation.size()
        footer_w, footer_h = self.footer.size()
        lines = self._wrap_words()
        sentence_w = max((w for _, w, _ in lines), default=0)

        right_w = mic_icon.size + 6 + score_w
        title_group_w = BADGE + BADGE_GAP + title_w
        width = max(MIN_WIDTH, header_w + 24 + right_w, title_group_w, sentence_w, translation_w,
                    BAR_MIN_WIDTH + 12 + footer_w) + 2 * PAD

        # Header row: language label left; green mic and score right
        y = PAD
        row_h = max(header_h, score_h, mic_icon.size)
        mid = y + row_h / 2
        self.header.place(PAD, mid, "w")
        self.score.place(width - PAD, mid, "e")
        c.coords(self.mic, width - PAD - score_w - 6, mid - mic_icon.size / 2)
        y += row_h + 8

        # Check badge with the title to its right, centred together
        row_h = max(BADGE, title_h)
        mid = y + row_h / 2
        left = (width - title_group_w) / 2
        c.coords(self.badge, left, mid - BADGE / 2, left + BADGE, mid + BADGE / 2)
        r = BADGE / 2
        cx = left + r
        c.coords(self.tick, cx - r * 0.42, mid, cx - r * 0.1, mid + r * 0.32, cx + r * 0.45, mid - r * 0.3)
        self.title.place(left + BADGE + BADGE_GAP, mid, "w")
        y += row_h + 8

        # The sentence, wrapped by hand so every word gets its own underline
        for line, line_w, line_h in lines:
            x = (width - line_w) / 2
            for word, (w, _) in line:
                word.place(x, y, "nw")
                c.coords(self._underlines[self._words.index(word)],
                         x, y + line_h + 1, x + w, y + line_h + 1 + UNDERLINE)
                x += w + self._space
            y += line_h + 1 + UNDERLINE + 4

        # Translation under it
        if translation_h:
            y += 2
            self.translation.place(width / 2, y, "n")
            y += translation_h

        # Footer: bar filling up until the next round may start, then the label
        y += 12
        row_h = max(footer_h, BAR_HEIGHT)
        mid = y + row_h / 2
        self.footer.place(width - PAD, mid, "e")
        bar_right = width - PAD - footer_w - 12
        top = mid - BAR_HEIGHT / 2
        c.coords(self.bar_track, PAD, top, bar_right, top + BAR_HEIGHT)
        self._bar = (PAD + 1, top + 1, bar_right - PAD - 2)
        self._draw_bar()
        y += row_h

        return width, y + PAD

    def _set_visible(self, visible: bool):
        self._visible = visible
        state = "normal" if visible else "hidden"
        for text in self._texts + self._words:
            text.set_visible(visible)
        for item in self._shapes + self._underlines:
            self.canvas.itemconfigure(item, state=state)

    # ---- Words ----

    def _build_words(self, sentence: str):
        for word in self._words:
            word.delete()
        for item in self._underlines:
            self.canvas.delete(item)
        self._words, self._underlines = [], []
        state = "normal" if self._visible else "hidden"
        for text in sentence.split():
            word = OutlinedText(self.canvas, SENTENCE_FONT, color_palette.TEXT)
            word.set(text)
            word.set_visible(self._visible)
            self._words.append(word)
            self._underlines.append(self.canvas.create_rectangle(
                0, 0, 0, 0, fill=color_palette.GREEN, width=0, state=state))

    def _wrap_words(self) -> list[tuple[list[tuple[OutlinedText, tuple[int, int]]], float, float]]:
        """Split the words into lines no wider than MAX_TEXT_WIDTH.
        Returns [(words with their sizes, line width, line height)]."""
        lines, line, line_w = [], [], 0.0
        for word in self._words:
            size = word.size()
            added = size[0] if not line else self._space + size[0]
            if line and line_w + added > MAX_TEXT_WIDTH:
                lines.append(line)
                line, added = [], size[0]
                line_w = 0.0
            line.append((word, size))
            line_w += added
        if line:
            lines.append(line)
        return [(ln, sum(s[0] for _, s in ln) + self._space * (len(ln) - 1), max(s[1] for _, s in ln))
                for ln in lines]

    def _measure_space(self) -> float:
        """Width of a space in the sentence font: Tk measures text, not lone spaces."""
        def width(text):
            item = self.canvas.create_text(-1000, -1000, text=text, font=SENTENCE_FONT)
            x1, _, x2, _ = self.canvas.bbox(item)
            self.canvas.delete(item)
            return x2 - x1
        return width("a a") - width("aa")

    # ---- Footer bar ----

    def _draw_bar(self):
        left, top, inner_w = self._bar
        frac = min(1.0, (time.monotonic() - self._shown_at) * 1000 / SUCCESS_MIN_SHOW_MS)
        self.canvas.coords(self.bar_fill, left, top, left + inner_w * frac, top + BAR_HEIGHT - 1)

    def _advance_bar(self):
        self._draw_bar()
        if (time.monotonic() - self._shown_at) * 1000 < SUCCESS_MIN_SHOW_MS:
            self._start_timer(FRAME_MS, self._advance_bar)
        else:
            self._timer_id = None
