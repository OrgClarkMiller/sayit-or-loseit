from dataclasses import dataclass
import threading
from piper import PiperVoice
from sentence_generation.sentence_generator import SentenceGenerator
from tray import TrayManager
from window import ConfigurationWindow
from window.overlay_window import OverlayWindow, ProcessingIndicator
import config
from sentence_generation.sentence_context_factory import sentence_context_factory, ContextKind
import time
from audio import phon, recording, speaking
from punishment import FailSeverity, get_fail_severity, punishment_factory

CONTEXT_READ_DELAY       = 10
VOICE_INPUT_MAX_ATTEMPTS = 3

# Holds refs to all essential components such as
#the tray, the different windows and things
#like stop events to make all windows and such
#close out properly

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
    generator: SentenceGenerator
    voice: PiperVoice  # loaded for target_lang, so playback always matches the sentence
    version: int       # which apply_config() these came from; older ones are out of date

# Mediator Class (child components talk to this to do things like program shutdown)
class AppContext:
    def __init__(self):
        self.stop_event = threading.Event()
        self.tray = TrayManager(self)
        self.tray_thread = threading.Thread(target=self.tray.run, daemon=True)
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)

        # Windows run on their own threads (started by .start()) and close on stop_event.
        # Their public methods are thread-safe, e.g. ctx.overlay.set_text("hi") from anywhere.
        self.overlay = None
        self._update_overlay(config.get_config().getboolean('Challenge', 'is_active')) # Show the overlay

        # The config window can be opened and closed repeatedly; a fresh one is made each time.
        self._windows_lock = threading.Lock()  # launches can come from the tray or worker thread
        self.config_window = None

        # Set by the config window to start a round right away instead of waiting out
        # CONTEXT_READ_DELAY. An Event, not a shared timestamp: the worker also writes its
        # timestamp after each round, which would overwrite a reset made meanwhile.
        self._run_now = threading.Event()
        # Wakes the worker from its 1 s sleep early: when settings become ready, so the
        # round starts straight after "Loading Language" (no gap showing the idle overlay),
        # and on quit.
        self._wake = threading.Event()

        # The settings rounds use. None until the first build finishes (the worker skips
        # rounds until then). Only ever replaced whole, never edited.
        self.settings: ChallengeSettings | None = None
        self._settings_version = 0     # bumped by each apply_config() that changes something
        self._requested_values = None  # the values that version was requested with
        self._version_lock = threading.Lock()  # guards the two above
        self._build_lock = threading.Lock()    # one build at a time

        self.apply_config()

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
        )
        with self._version_lock:
            if values == self._requested_values:
                return  # nothing changed (e.g. the config window was just opened and closed)
            self._requested_values = values
            self._settings_version += 1
            version = self._settings_version
        threading.Thread(target=self._build_settings, args=(values, version), daemon=True).start()

    def _is_latest_settings(self, version: int) -> bool:
        with self._version_lock:
            return version == self._settings_version

    def _build_settings(self, values: dict, version: int):
        """Background thread: load everything for `values`, then publish it in one go."""
        with self._build_lock:
            # Saved again while this one waited its turn: skip it, the newer build wins
            if not self._is_latest_settings(version):
                return
            target_lang = values["target_lang"]
            print(f"Loading settings for {target_lang}")
            with ProcessingIndicator(self.overlay, "Loading Language"):
                phon.init_lang(target_lang)  # warm up espeak so the first round isn't slow
                settings = ChallengeSettings(
                    target_lang=target_lang,
                    proficiency=values["proficiency"],
                    playback=values["playback"],
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
                if self._is_latest_settings(version):
                    self.settings = settings  # one assignment: rounds see all old or all new
                    self._wake.set()  # let the worker start a round now, not up to 1 s later
                    print(f"Settings for {target_lang} ready")

    def on_change_challenge_status(self):
        print('on_change_challenge_status()')
        self._run_now.set()  # make the challenge start right away
        self._wake.set()

    def start(self):
        # The overlay isn't started here: _update_overlay starts it whenever it creates one
        self.tray_thread.start()
        self.worker_thread.start()
        phon.init_model()  # load the 1.3 GB phoneme model up front rather than mid-round

    def join(self):
        self.tray_thread.join()
        self.worker_thread.join()
        if self.overlay is not None:
            self.overlay.join()
        if self.config_window is not None:
            self.config_window.join()  # let it save its settings before main.py writes them

    def stop(self):
        self.stop_event.set()  # closes the tray, the worker loop and the overlay
        self._wake.set()       # the worker sleeps on _wake, so wake it to see stop_event

    def launch_config_window(self):
        """Show the configuration window. Does nothing if it's already open."""
        with self._windows_lock:
            if self.config_window is not None and self.config_window.is_alive():
                return
            self.config_window = ConfigurationWindow(self)
            self.config_window.start()

    # The main work being done by the worker thread
    def worker(self):
        """Worker loop: runs until the user clicks Quit in the tray."""
        prev_challenge_time = None  # only this thread uses it; others ask via _run_now
        while not self.stop_event.is_set():
            # Cleared before looking at any state: a wake-up arriving during this pass stays
            # set, so the wait below returns at once and the next pass sees the change.
            self._wake.clear()
            # TODO: poll / handle system events here
            print("checking for events...")

            conf = config.get_config()
            is_active = conf.getboolean('Challenge', 'is_active')

            self._update_overlay(is_active)
            settings = self.settings  # take the current settings once, for this whole round
            # Wait while settings are loading: at startup (None), and after a change until
            # the new ones are ready. Otherwise the round right after saving, started
            # straight away by _run_now, would still use the old language.
            ready = settings is not None and self._is_latest_settings(settings.version)
            if is_active and ready:
                now = time.perf_counter()
                due = prev_challenge_time is None or now - prev_challenge_time > CONTEXT_READ_DELAY
                if due or self._run_now.is_set():
                    self._run_now.clear()
                    self._run_challenge(settings)
                    prev_challenge_time = now

            # Like sleep(1), but returns immediately when woken: on quit, when new settings
            # are ready, or when the config window asks for a round now.
            self._wake.wait(1)

        print("worker shutting down")

    def _update_overlay(self, show):
        if not show and self.overlay is not None:
            self.overlay.close()
            self.overlay = None # Delete Overlay
        elif show and self.overlay is None:
            self.overlay = OverlayWindow(self)
            self.overlay.start()  # a window only appears once started

    def _challenge_still_wanted(self, settings: ChallengeSettings) -> bool:
        """False once the user quits, turns challenges off, or saves new settings (the
        round's language or proficiency is then out of date; the next round uses the new
        ones). A round takes a while (Gemini, playback, recording), so it checks this
        between steps and stops early if so."""
        if self.stop_event.is_set():
            return False
        if not self._is_latest_settings(settings.version):
            return False
        return config.get_config().getboolean('Challenge', 'is_active')

    # Retry n times until perfect
    def _compare_voice_input(self, settings: ChallengeSettings, sent_phonetics: list[str], estimated_duration: float) -> FailSeverity:
        attempts = []

        for attempt_num in range(1, VOICE_INPUT_MAX_ATTEMPTS + 1):
            if not self._challenge_still_wanted(settings): return FailSeverity.PERFECT # TODO: Any potential cleanup

            self.overlay.set_attempt(attempt_num, VOICE_INPUT_MAX_ATTEMPTS)
            self.overlay.set_recording(True, estimated_duration)
            wav = recording.record(estimated_duration)
            self.overlay.set_recording(False)

            if not self._challenge_still_wanted(settings):  # turned off while recording: no score, no punishment
                return FailSeverity.PERFECT
            resp_phon = phon.generate(wav, settings.target_lang)

            percent_similar = phon.similarity(sent_phonetics, resp_phon)
            self.overlay.set_similarity_percent(percent_similar)

            fail_severity = get_fail_severity(percent_similar)
            if fail_severity < FailSeverity.MEDIUM:
                return fail_severity

            attempts.append(fail_severity) # Add to attempts
            time.sleep(1.5) # Sleep for 1.5 seconds so that the percent is visible and you can see how you did

        if len(attempts) == 0:
            return FailSeverity.PERFECT

        return min(attempts) # Retrun only best attempt

    def _run_challenge(self, settings: ChallengeSettings):
        """One round. Uses only `settings` (never the live config or self.settings), so
        saving new settings mid-round can't mix languages or proficiencies."""
        print('_run_challenge()')

        s_ctx = sentence_context_factory(ContextKind.SCREEN_IMAGE)
        if s_ctx is None:
            return

        # 1. Generate Sentence and phonetics (and set loading status)
        with ProcessingIndicator(self.overlay, "Generating Sentence"):
            gen = settings.generator.generate(s_ctx)

        if not self._challenge_still_wanted(settings):  # the Gemini call can take a few seconds
            return

        # 2.

        target_lang = settings.target_lang
        proficiency = settings.proficiency

        self.overlay.set_language_label(target_lang, proficiency)  # new: fills the header
        self.overlay.set_source_lang_sentence(gen.source_lang)
        self.overlay.set_target_lang_sentence(gen.target_lang)

        sent_phon = phon.generate(gen.target_lang, target_lang)

        if settings.playback:
            speaking.speak(sent_phon, settings.voice)
            if not self._challenge_still_wanted(settings):  # don't start recording if they turned it off mid-playback
                return

        est_dur = phon.speak_duration_estimate(sent_phon, proficiency)

        fail_severity = self._compare_voice_input(settings, sent_phon, est_dur)
        if not self._challenge_still_wanted(settings): return

        # Onlish punish if they actually deserve it
        if fail_severity > FailSeverity.CLOSE:
            pun = punishment_factory(fail_severity)
            if pun is not None:
                pun.punish()
            else: print("No punishment available")