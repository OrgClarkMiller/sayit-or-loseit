import time
import tkinter as tk
from typing import TYPE_CHECKING

import color_palette  # project root module, not part of the window package
from screen_io.screen_capture import exclude_from_capture, user32

from ..window import MARGIN, Window, WindowPosition
from ..window_helpers import app_window_below, hwnd, is_app_window, make_click_through, round_corners
from .images import tinted_frames, tinted_icon
from .states import ChallengeState, OverlayState, ProcessingState, PunishmentState
from .style import MIC_IDLE_COLOR, MIC_RECORDING_COLOR, TRANSPARENT, loading_gif_icon, mic_icon
from .views import ContentView, OverlayView, ProcessingView, PunishmentView

if TYPE_CHECKING:  # forward ref: app_context imports this module, so a real import would be circular
    from app_context import AppContext


class OverlayWindow(Window):
    """Always-on-top, click-through overlay on a see-through background, showing one
    OverlayState at a time (see states.py for what each looks like).

    Everything is drawn on one canvas so text can get a dark outline. Each kind of
    state has a view that draws it; render_state() picks the view by the state's type.

    Construct it, then start(). render_state() and clear_state() are safe to call from
    any thread. It closes when the app's stop_event is set.
    """

    def __init__(self, app_context: "AppContext", initial_state: OverlayState | None = None):
        """initial_state defaults to a "Loading..." spinner, shown until something
        renders another state. Pass ChallengeState() to open straight to the content."""
        super().__init__(app_context)
        self._initial_state = initial_state or ProcessingState("Loading...")

    # ---- Thread-safe API ----

    def render_state(self, state: OverlayState):
        """Show `state`. A ChallengeState is also remembered as the round's content,
        which clear_state() goes back to.

        A state of a different kind may not appear at once: the one showing can hold
        the screen a moment longer (OverlayState.hold_ms), e.g. so an instant
        punishment can still be read."""
        self.call(self._render_state, state)

    def clear_state(self, state: OverlayState):
        """Go back to the round's content, if `state` (this exact object) is still the
        one showing or waiting to show. Otherwise someone else has replaced it since,
        and this does nothing."""
        self.call(self._clear_state, state)

    # ---- Tk thread: states ----

    def _view_for(self, state: OverlayState) -> OverlayView:
        match state:
            case ChallengeState():
                return self._content_view
            case ProcessingState():
                return self._processing_view
            case PunishmentState():
                return self._punishment_view
        raise TypeError(f"No overlay view for {type(state).__name__}")

    def _render_state(self, state: OverlayState):
        if isinstance(state, ChallengeState):
            self._content = state
        self._cancel_pending()

        current = self._current
        if current is not None and type(state) is not type(current):
            delay = current.hold_ms((time.monotonic() - self._shown_at) * 1000)
            if delay > 0:
                self._pending = state
                self._pending_id = self.root.after(delay, self._apply_pending)
                return
        self._apply(state)

    def _clear_state(self, state: OverlayState):
        if state is self._current or state is self._pending:
            self._render_state(self._content)

    def _apply_pending(self):
        state, self._pending, self._pending_id = self._pending, None, None
        self._apply(state)

    def _cancel_pending(self):
        if self._pending_id is not None:
            self.root.after_cancel(self._pending_id)
        self._pending = self._pending_id = None

    def _apply(self, state: OverlayState):
        view = self._view_for(state)
        if view is not self._current_view:
            if self._current_view is not None:
                self._current_view.leave()
            view.enter()
            self._current_view = view
        if self._current is None or type(state) is not type(self._current):
            self._shown_at = time.monotonic()  # a new punishment replacing one doesn't restart the clock
        self._current = state
        view.update(state)
        self._layout()

    def _layout(self):
        """Lay out the visible view, then re-fit the window around it."""
        width, height = self._current_view.layout()
        c = self.canvas
        if (int(c.cget("width")), int(c.cget("height"))) != (int(width), int(height)):
            c.config(width=width, height=height)
            self.place_window_at(WindowPosition.LOWER_CENTER)  # re-fit and re-center

    # ---- Tk thread: window ----

    def build(self):
        # Keep references: Tk drops an image once Python frees it
        self.mic_idle_icon      = tinted_icon(self.root, mic_icon.path, mic_icon.size, MIC_IDLE_COLOR)
        self.mic_recording_icon = tinted_icon(self.root, mic_icon.path, mic_icon.size, MIC_RECORDING_COLOR)
        self.loading_frames     = tinted_frames(self.root, loading_gif_icon.path, loading_gif_icon.size)  # untinted

        # Translucent dark panel behind the text. A window can either key out one color
        # fully (the text window does that) or fade as a whole (which would fade the text
        # too), so the panel is its own faded window that follows the text window around.
        self.backdrop = tk.Toplevel(self.root, bg=color_palette.BACKDROP)
        self.backdrop.overrideredirect(True)
        self.backdrop.attributes("-topmost", True)
        self.backdrop.attributes("-alpha", 0.0)  # hidden until on_show() has positioned it

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._content_view    = ContentView(self.canvas, self._layout, self.mic_idle_icon, self.mic_recording_icon)
        self._processing_view = ProcessingView(self.canvas, self._layout, self.loading_frames)
        self._punishment_view = PunishmentView(self.canvas, self._layout)

        self._content = ChallengeState()             # what clear_state() goes back to
        self._current: OverlayState | None = None    # showing now
        self._current_view: OverlayView | None = None
        self._shown_at = 0.0                         # when the current kind of state appeared
        self._pending: OverlayState | None = None    # waiting for the current one's hold_ms
        self._pending_id: str | None = None

        self._render_state(self._initial_state)

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

    def _release_tk(self):
        # The views hold the canvas and images but aren't Tk objects themselves, so the
        # base class wouldn't drop them: do it here, so they're freed on the Tk thread
        self._content_view = self._processing_view = self._punishment_view = self._current_view = None
        super()._release_tk()
