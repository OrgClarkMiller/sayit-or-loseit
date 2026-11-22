import tkinter as tk

import color_palette  # project root module, not part of the window package

# The 8 neighbours get a dark copy; (0, 0), last, is the coloured copy on top
_OFFSETS = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1), (0, 0)]


class OutlinedText:
    """A canvas text with a 1 px dark outline: 8 dark copies around one coloured copy.
    With no card behind the overlay's text, the outline keeps it readable over both
    light and dark windows. Starts hidden."""

    def __init__(self, canvas: tk.Canvas, font: tuple, color: str, wrap: int = 0):
        self._canvas = canvas
        self._items: list[tuple[int, int, int]] = []  # (item, dx, dy)
        for dx, dy in _OFFSETS:
            fill = color if (dx, dy) == (0, 0) else color_palette.OUTLINE
            item = canvas.create_text(0, 0, text="", font=font, fill=fill, width=wrap,
                                      justify="center", state="hidden")
            self._items.append((item, dx, dy))

    @property
    def _main(self) -> int:
        return self._items[-1][0]

    def set(self, text: str, color: str | None = None):
        for item, _, _ in self._items:
            self._canvas.itemconfigure(item, text=text)
        if color is not None:
            self._canvas.itemconfigure(self._main, fill=color)

    def size(self) -> tuple[int, int]:
        """(width, height) in px; (0, 0) when empty."""
        if not self._canvas.itemcget(self._main, "text"):
            return 0, 0
        x1, y1, x2, y2 = self._canvas.bbox(self._main)
        return x2 - x1, y2 - y1

    def place(self, x: float, y: float, anchor: str):
        for item, dx, dy in self._items:
            self._canvas.coords(item, x + dx, y + dy)
            self._canvas.itemconfigure(item, anchor=anchor)

    def set_visible(self, visible: bool):
        state = "normal" if visible else "hidden"
        for item, _, _ in self._items:
            self._canvas.itemconfigure(item, state=state)
