"""What the overlay can show. Pass one to OverlayWindow.render_state().

States are immutable, so any thread can build one and hand it over. To change what's
shown, render a new one, e.g. dataclasses.replace(state, similarity_percent=87).

eq=False on each: states are compared by identity, so clear_state() only clears the
exact state its caller rendered, not an equal-looking one rendered by someone else.
"""
import time
from dataclasses import dataclass, field

from punishment.fail_severity import FailSeverity

PROCESSING_HIDE_GRACE_MS = 400  # how long the spinner lingers in case another loading step follows
PUNISHMENT_MIN_SHOW_MS = 2500   # instant punishments (a tab closing) still get read before the round's content returns


class OverlayState:
    """Base class for everything the overlay can show."""

    def hold_ms(self, shown_for_ms: float) -> int:
        """How much longer this state stays on screen once a different kind of state
        replaces it, given how long it's been showing. A state of the same kind always
        replaces it at once."""
        return 0


@dataclass(frozen=True, eq=False)
class ProcessingState(OverlayState):
    """Only the loading spinner, with an optional message beside it, e.g.
    "Generating Sentence"."""
    message: str = ""

    def hold_ms(self, shown_for_ms: float) -> int:
        # One loading step often ends just before the next begins ("Loading Language" ->
        # "Generating Sentence"): lingering stops the content flashing up in between
        return PROCESSING_HIDE_GRACE_MS


@dataclass(frozen=True, eq=False)
class PunishmentState(OverlayState):
    """Only the punishment being applied, e.g. ("Close Media", SEVERE):

                PUNISHMENT  ·  SEVERE
                     Close Media
    """
    name: str
    severity: FailSeverity | None = None

    def hold_ms(self, shown_for_ms: float) -> int:
        return max(0, int(PUNISHMENT_MIN_SHOW_MS - shown_for_ms))


@dataclass(frozen=True)
class Recording:
    """The mic is live. Build it when recording starts: it times from its creation."""
    seconds: float | None = None  # time to speak; None or 0 shows "REC" without a countdown
    started_at: float = field(default_factory=time.monotonic)

    @property
    def has_countdown(self) -> bool:
        return bool(self.seconds)

    def seconds_left(self) -> float:
        return max(0.0, self.started_at + (self.seconds or 0) - time.monotonic())

    def fraction_left(self) -> float:
        return self.seconds_left() / self.seconds if self.seconds else 0.0


@dataclass(frozen=True, eq=False)
class ChallengeState(OverlayState):
    """The round's content:

        FRENCH · A2                        ● 🎤 REC 4s
        Attempt 1 of 3
               Le chat dort sur le canapé rouge.
                 the cat sleeps on the red sofa
        ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬────────────────────────   (while recording)

    The status on the right is the REC countdown while recording, else the score.
    """
    language: str = ""
    level: str = ""
    target_sentence: str = ""   # the sentence to say
    source_sentence: str = ""   # its translation, shown under it
    attempt: int | None = None
    max_attempts: int | None = None
    recording: Recording | None = None
    similarity_percent: float | None = None


@dataclass(frozen=True, eq=True)
class SuccessState(OverlayState):
    similarity: float = ""
    target_sentence: str = ""