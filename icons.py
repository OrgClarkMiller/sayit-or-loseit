
from pathlib import Path

ROOT_DIR = Path(__file__).parent
IMAGES_DIR = ROOT_DIR / "assets" / "image"

class Icon:
    """A square image in assets/, drawn at size x size px."""
    def __init__(self, name: str, size: int):
        self.path = IMAGES_DIR / name
        self.size = size  # one number: used in layout maths, so not a (w, h) tuple

    @property
    def dimensions(self) -> tuple[int, int]:
        """(width, height), for things like PIL's resize()"""
        return self.size, self.size

class GifIcon(Icon):
    def __init__(self, name: str, size: int, frame_duration: int):
        super().__init__(name, size)
        self.frame_duration = frame_duration  # ms; an int, since Tk's after() rejects floats