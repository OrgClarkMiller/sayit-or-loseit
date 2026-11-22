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
RESULT_SHOW_MS = 1500           # how long a round's result (punishment or success) stays up before the next screen
PUNISHMENT_MIN_SHOW_MS = RESULT_SHOW_MS  # instant punishments (a tab closing) still get read
SUCCESS_MIN_SHOW_MS = RESULT_SHOW_MS


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


@dataclass(frozen=True, eq=False)
class SuccessState(OverlayState):
    """Shown instead of a punishment when the sentence passed (PERFECT in green, CLOSE in lime):

        FRENCH · A2                             🎤 96%
                       ✔ Nailed it!
               Le chat dort sur le canapé rouge.
               ‾‾ ‾‾‾‾ ‾‾‾‾ ‾‾‾ ‾‾ ‾‾‾‾‾‾ ‾‾‾‾‾‾
                 the cat sleeps on the red sofa
        ▬▬▬▬▬▬▬▬▬▬───────────────   No punishment · next round
    """
    similarity: float = 0.0
    target_sentence: str = ""
    source_sentence: str = ""
    language: str = ""
    level: str = ""

    @classmethod
    def from_challenge(cls, state: ChallengeState, similarity: float) -> "SuccessState":
        return cls(similarity, state.target_sentence, state.source_sentence, state.language, state.level)

    def hold_ms(self, shown_for_ms: float) -> int:
        return max(0, int(SUCCESS_MIN_SHOW_MS - shown_for_ms))