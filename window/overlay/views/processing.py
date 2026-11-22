from typing import Callable
import tkinter as tk

import color_palette  # project root module, not part of the window package

from ..outlined_text import OutlinedText
from ..states import ProcessingState
from ..style import MAX_TEXT_WIDTH, MIN_WIDTH, PAD, SMALL_FONT, loading_gif_icon
from .base import OverlayView

GAP = 8  # px between the spinner and its message


class ProcessingView(OverlayView[ProcessingState]):
    """The loading spinner with its message to the right, centred together."""

    def __init__(self, canvas: tk.Canvas, request_layout: Callable[[], None], frames: list[tk.PhotoImage]):
        super().__init__(canvas, request_layout)
        self._frames = frames
        self._frame = 0
        self.spinner = canvas.create_image(0, 0, image=frames[0], anchor="nw", state="hidden")
        self.message = OutlinedText(canvas, SMALL_FONT, color_palette.MUTED, wrap=MAX_TEXT_WIDTH)

    def enter(self):
        super().enter()
        self._frame = 0
        self._spin()  # only on enter: a new message mustn't restart the animation

    def update(self, state: ProcessingState):
        self.message.set(state.message)

    def layout(self) -> tuple[float, float]:
        icon = loading_gif_icon.size
        msg_w, msg_h = self.message.size()
        group_w = icon + (GAP + msg_w if msg_w else 0)
        row_h = max(icon, msg_h)
        width = max(MIN_WIDTH, group_w) + 2 * PAD
        left = (width - group_w) / 2
        mid = PAD + row_h / 2
        self.canvas.coords(self.spinner, left, mid - icon / 2)
        self.message.place(left + icon + GAP, mid, "w")
        return width, row_h + 2 * PAD

    def _set_visible(self, visible: bool):
        self.canvas.itemconfigure(self.spinner, state="normal" if visible else "hidden")
        self.message.set_visible(visible)

    def _spin(self):
        """Show the next frame of the loading GIF, then keep going until leave()."""
        self.canvas.itemconfigure(self.spinner, image=self._frames[self._frame])
        self._frame = (self._frame + 1) % len(self._frames)
        self._start_timer(loading_gif_icon.frame_duration, self._spin)
