from enum import StrEnum

from sentence_generator import (
    ISentenceContext,
    ImageSentenceContext,
    ScreenTextSentenceContext,
    TranscriptSentenceContext,
)

from screen_io.read_screen_text import read_screen_text
from screen_io.screen_capture import capture_focused_window


class ContextKind(StrEnum):
    """What a sentence is generated from. StrEnum so it can come from config or text."""
    TRANSCRIPT = "transcript"
    SCREEN_TEXT = "screen_text"
    SCREEN_IMAGE = "screen_image"

def sentence_context_factory(kind: ContextKind | str) -> ISentenceContext | None:
    """Returns None when there's nothing to build a context from (e.g. no focused window)."""
    match kind:
        case ContextKind.SCREEN_IMAGE:
            wnd = capture_focused_window()
            return ImageSentenceContext(wnd.image) if wnd is not None else None
        case ContextKind.SCREEN_TEXT: return ScreenTextSentenceContext(read_screen_text())
        case ContextKind.TRANSCRIPT: raise NotImplementedError("Haven't impd transcript yet")