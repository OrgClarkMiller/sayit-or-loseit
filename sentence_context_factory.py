from enum import StrEnum

from sentence_generator import (
    ISentenceContext,
    ObjectSentenceContext,
    ScreenTextSentenceContext,
    TranscriptSentenceContext,
)

from read_screen_text import read_screen_text


class ContextKind(StrEnum):
    """What a sentence is generated from. StrEnum so it can come from config or text."""
    OBJECT = "object"
    TRANSCRIPT = "transcript"
    SCREEN_TEXT = "screen_text"

def sentence_context_factory(kind: ContextKind | str) -> ISentenceContext:
    match kind:
        case ContextKind.OBJECT: raise NotImplementedError("Haven't impd object list yet")
        case ContextKind.SCREEN_TEXT: return ScreenTextSentenceContext(read_screen_text())
        case ContextKind.TRANSCRIPT: raise NotImplementedError("Haven't impd transcript yet")