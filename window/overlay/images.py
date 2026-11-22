import base64
import io
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageSequence

from .style import TRANSPARENT_RGB


def tinted_frames(master, path: Path, size: int, color: tuple[int, int, int] | None = None) -> list[tk.PhotoImage]:
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


def tinted_icon(master, path: Path, size: int, color: tuple[int, int, int]) -> tk.PhotoImage:
    """A single-frame icon, shrunk and filled with one solid color."""
    return tinted_frames(master, path, size, color)[0]
