from dataclasses import dataclass
import threading
from typing import Callable

from piper import PiperVoice

import config
from audio import phon, speaking
from sentence_generation.sentence_generator import SentenceGenerator
from window.overlay_window import OverlayWindow, ProcessingIndicator


@dataclass(frozen=True)
class ChallengeSettings:
    """Everything one challenge round depends on, built together and never changed.

    The config window saves on its own thread while a round may be running. Instead of
    the round reading settings one at a time from the shared config (and getting a mix
    of old and new values), a complete new ChallengeSettings is built in the background
    and swapped in with one assignment. A round grabs it once at the start and finishes
    with those settings, even if new ones arrive meanwhile.
    """
    target_lang: str
    proficiency: str
    playback: bool
    max_attempts: int  # recordings per round, including the first
    generator: SentenceGenerator
    voice: PiperVoice  # loaded for target_lang, so playback always matches the sentence
    version: int       # which apply_config() these came from; older ones are out of date


class SettingsStore:
    """Builds ChallengeSettings from the config in the background and hands out the latest.

    get_overlay: returns the overlay to show "Loading Language" on (or None). A getter,
        not the overlay itself: builds run on their own thread, and the overlay can be
        replaced or removed while one runs.
    on_ready: called once new settings are published, e.g. to wake the scheduler.
    """

    def __init__(self, get_overlay: Callable[[], OverlayWindow | None], on_ready: Callable[[], None]):
        self._get_overlay = get_overlay
        self._on_ready = on_ready

        # The settings rounds use. None until the first build finishes. Only ever
        # replaced whole, never edited.
        self._settings: ChallengeSettings | None = None
        self._version = 0              # bumped by each apply_config() that changes something
        self._requested_values = None  # the values that version was requested with
        self._version_lock = threading.Lock()  # guards the two above
        self._build_lock = threading.Lock()    # one build at a time

    def apply_config(self):
        """Rebuild the challenge settings from the current config. Call after changing it.

        Returns straight away: loading a language's espeak backend and Piper voice takes
        seconds, so it happens on a background thread, and rounds keep using the old
        settings until the new ones are ready.
        """
        # Read every value now, on the caller's thread, right after it finished writing
        # them, so a later save can't change them while the build is running.
        conf = config.get_config()
        values = dict(
            source_lang=conf.get("Language", "source"),
            target_lang=conf.get("Language", "target"),
            proficiency=conf.get("Language", "proficiency"),
            max_words=conf.getint("Sentence", "max_words"),
            gemini_api_key=conf.get("AI", "gemini_key"),
            playback=conf.getboolean("Challenge", "playback"),
            num_tries=conf.getint("Challenge", "num_tries"),
        )
        with self._version_lock:
            if values == self._requested_values:
                return  # nothing changed (e.g. the config window was just opened and closed)
            self._requested_values = values
            self._version += 1
            version = self._version
        threading.Thread(target=self._build, args=(values, version), daemon=True).start()

    def current(self) -> ChallengeSettings | None:
        """The settings to start a round with, or None while they're loading: at startup,
        and after a change until the new ones are ready. Otherwise the round right after
        saving would still use the old language."""
        settings = self._settings  # read once: another thread may replace it
        if settings is None or not self.is_latest(settings):
            return None
        return settings

    def is_latest(self, settings: ChallengeSettings) -> bool:
        """False once newer settings have been requested (even if not built yet)."""
        return self._is_latest_version(settings.version)

    def _is_latest_version(self, version: int) -> bool:
        with self._version_lock:
            return version == self._version

    def _build(self, values: dict, version: int):
        """Background thread: load everything for `values`, then publish it in one go."""
        with self._build_lock:
            # Saved again while this one waited its turn: skip it, the newer build wins
            if not self._is_latest_version(version):
                return
            target_lang = values["target_lang"]
            print(f"Loading settings for {target_lang}")
            with ProcessingIndicator(self._get_overlay(), "Loading Language"):
                phon.init_lang(target_lang)  # warm up espeak so the first round isn't slow
                settings = ChallengeSettings(
                    target_lang=target_lang,
                    proficiency=values["proficiency"],
                    playback=values["playback"],
                    max_attempts=max(1, values["num_tries"]),  # never 0: a hand-edited conf.ini could say so
                    generator=SentenceGenerator(
                        source_lang=values["source_lang"],
                        target_lang=target_lang,
                        proficiency=values["proficiency"],
                        max_words=values["max_words"],
                        gemini_api_key=values["gemini_api_key"],
                    ),
                    voice=speaking.get_voice(target_lang),
                    version=version,
                )
                if self._is_latest_version(version):
                    self._settings = settings  # one assignment: rounds see all old or all new
                    self._on_ready()  # let a round start now, not up to 1 s later
                    print(f"Settings for {target_lang} ready")
