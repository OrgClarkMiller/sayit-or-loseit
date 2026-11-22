from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar
import tkinter as tk

from ..states import OverlayState

S = TypeVar("S", bound=OverlayState)


class OverlayView(ABC, Generic[S]):
    """Draws one kind of OverlayState on the shared canvas. Tk thread only.

    The overlay shows one view at a time: enter() when it becomes the visible one,
    update() with each state it should show, leave() when another view takes over.
    After every update() the overlay calls layout() and fits the window to the size
    it returns. A view whose content changes by itself (e.g. a countdown) calls
    request_layout() to have that happen again.
    """

    def __init__(self, canvas: tk.Canvas, request_layout: Callable[[], None]):
        self.canvas = canvas
        self.request_layout = request_layout
        self._timer_id: str | None = None

    def enter(self):
        self._set_visible(True)

    def leave(self):
        self._stop_timer()
        self._set_visible(False)

    @abstractmethod
    def update(self, state: S):
        """Show `state`'s content. Positioning is left to layout()."""

    @abstractmethod
    def layout(self) -> tuple[float, float]:
        """Position this view's items; return the (width, height) they need."""

    @abstractmethod
    def _set_visible(self, visible: bool):
        """Show or hide all of this view's canvas items."""

    # ---- One repeating timer per view (an animation or a countdown) ----

    def _start_timer(self, ms: int, callback: Callable[[], None]):
        self._stop_timer()
        self._timer_id = self.canvas.after(ms, callback)

    def _stop_timer(self):
        if self._timer_id is not None:
            self.canvas.after_cancel(self._timer_id)
            self._timer_id = None
