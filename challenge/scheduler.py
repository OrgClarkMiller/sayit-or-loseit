import threading
import time
from typing import Callable

import config
from window.overlay_window import OverlayWindow

from .round import ChallengeRound
from .settings import ChallengeSettings, SettingsStore

CONTEXT_READ_DELAY = 10  # seconds between rounds


class ChallengeScheduler:
    """The worker loop: decides when a round runs, and runs it.

    stop_event: the loop ends once it's set.
    settings: where each round's settings come from.
    update_overlay: shows (True) or removes (False) the overlay, returning the current
        one (None when removed). Called every pass, so the overlay follows the
        is_active setting.
    """

    def __init__(self, stop_event: threading.Event, settings: SettingsStore,
                 update_overlay: Callable[[bool], OverlayWindow | None],
                 delay: float = CONTEXT_READ_DELAY):
        self._stop_event = stop_event
        self._settings = settings
        self._update_overlay = update_overlay
        self._delay = delay

        # Set to start a round right away instead of waiting out the delay. An Event,
        # not a shared timestamp: the loop also writes its timestamp after each round,
        # which would overwrite a reset made meanwhile.
        self._run_now = threading.Event()
        # Wakes the loop from its 1 s sleep early: when settings become ready, so the
        # round starts straight after "Loading Language" (no gap showing the idle
        # overlay), and on quit.
        self._wake = threading.Event()

    # ---- Thread-safe API ----

    def run_now(self):
        """Start a round right away, without waiting out the delay."""
        self._run_now.set()
        self._wake.set()

    def wake(self):
        """Re-check straight away (e.g. new settings are ready, or quitting)."""
        self._wake.set()

    # ---- Worker thread ----

    def run(self):
        """Runs until stop_event is set. The worker thread's target."""
        prev_challenge_time = None
        while not self._stop_event.is_set():
            # Cleared before looking at any state: a wake-up arriving during this pass stays
            # set, so the wait below returns at once and the next pass sees the change.
            self._wake.clear()

            is_active = _is_active()
            overlay = self._update_overlay(is_active)
            settings = self._settings.current()  # taken once, for this whole round
            if is_active and settings is not None and overlay is not None:
                now = time.perf_counter()
                due = prev_challenge_time is None or now - prev_challenge_time > self._delay
                if due or self._run_now.is_set():
                    self._run_now.clear()
                    ChallengeRound(settings, overlay, lambda: self._still_wanted(settings)).run()
                    prev_challenge_time = now

            self._wake.wait(1)

        print("scheduler shutting down")

    def _still_wanted(self, settings: ChallengeSettings) -> bool:
        """False once the user quits, turns challenges off, or saves new settings (the
        round's language or proficiency is then out of date; the next round uses the
        new ones)."""
        if self._stop_event.is_set():
            return False
        if not self._settings.is_latest(settings):
            return False
        return _is_active()


def _is_active() -> bool:
    return config.get_config().getboolean('Challenge', 'is_active')
