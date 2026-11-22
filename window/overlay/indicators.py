"""with blocks that show a state on the overlay for as long as an operation runs."""
from typing import TYPE_CHECKING

from punishment.fail_severity import FailSeverity

from .states import OverlayState, ProcessingState, PunishmentState

if TYPE_CHECKING:  # only for the annotations
    from .overlay_window import OverlayWindow


class StateIndicator:
    """Shows `state` while the block runs, then goes back to the round's content (unless
    something else replaced it in the meantime). Does nothing when overlay is None."""

    def __init__(self, overlay: "OverlayWindow | None", state: OverlayState):
        self._overlay = overlay
        self.state = state

    def __enter__(self):
        if self._overlay is not None:
            self._overlay.render_state(self.state)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._overlay is not None:
            self._overlay.clear_state(self.state)
        return False  # Don't suppress exceptions


class ProcessingIndicator(StateIndicator):
    """The loading spinner (with `message`) until the operation completes."""

    def __init__(self, overlay: "OverlayWindow | None", message: str = ""):
        super().__init__(overlay, ProcessingState(message))


class PunishmentIndicator(StateIndicator):
    """Which punishment is being applied, for as long as the block runs (and a moment
    after, see PUNISHMENT_MIN_SHOW_MS)."""

    def __init__(self, overlay: "OverlayWindow | None", name: str, severity: FailSeverity | None = None):
        super().__init__(overlay, PunishmentState(name, severity))
