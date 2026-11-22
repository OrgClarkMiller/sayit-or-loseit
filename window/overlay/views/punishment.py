import color_palette  # project root module, not part of the window package
from punishment.fail_severity import FAIL_SEVERITY_COLOR

from ..outlined_text import OutlinedText
from ..states import PunishmentState
from ..style import HEADER_FONT, MAX_TEXT_WIDTH, MIN_WIDTH, PAD, SENTENCE_FONT
from .base import OverlayView


class PunishmentView(OverlayView[PunishmentState]):
    """The severity title with the punishment's name under it, both centred."""

    def __init__(self, canvas, request_layout):
        super().__init__(canvas, request_layout)
        self.title = OutlinedText(canvas, HEADER_FONT, color_palette.RED)
        self.name = OutlinedText(canvas, SENTENCE_FONT, color_palette.TEXT, wrap=MAX_TEXT_WIDTH)

    def update(self, state: PunishmentState):
        if state.severity is None:
            self.title.set("PUNISHMENT", color_palette.RED)
        else:
            self.title.set(f"PUNISHMENT  ·  {state.severity.name}", FAIL_SEVERITY_COLOR[state.severity])
        self.name.set(state.name)

    def layout(self) -> tuple[float, float]:
        title_w, title_h = self.title.size()
        name_w, name_h = self.name.size()
        width = max(MIN_WIDTH, title_w, name_w) + 2 * PAD
        y = PAD
        self.title.place(width / 2, y, "n")
        y += title_h + 4
        self.name.place(width / 2, y, "n")
        y += name_h
        return width, y + PAD

    def _set_visible(self, visible: bool):
        self.title.set_visible(visible)
        self.name.set_visible(visible)
