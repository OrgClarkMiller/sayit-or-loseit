import threading
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

        self.apply_config()

    def apply_config(self):
        """Push the current config into long-lived components. Call after config changes.

        Swaps in a whole new generator rather than editing the old one, so the worker
        thread sees either the old settings or the new ones, never a mix.
        """
        conf = config.get_config()
        self.generator = SentenceGenerator(
            source_lang=conf.get("Language", "source"),
            target_lang=conf.get("Language", "target"),
            proficiency=conf.get("Language", "proficiency"),
            max_words=conf.getint("Sentence", "max_words"),
            gemini_api_key=conf["AI"]["gemini_key"]
        )

    def on_change_target_language(self):
        print('on_change_target_language')
        # Initialize the backend rightaway since it takes a long time
        target_lang = config.get_config().get("Language", "target")
        print(f"Initializing {target_lang}'s phonetic backend")
        phon.init_lang(target_lang)
        speaking.load_voice(target_lang)  # the target language's voice, not the English default
        print(f"Finished initializing {target_lang}'s phonetic backend")

    def _init_backends(self):
        self.on_change_target_language()
        phon.init_model()

    def start(self):
        # The overlay isn't started here: _update_overlay starts it whenever it creates one
        self.tray_thread.start()
        self.worker_thread.start()
        self._init_backends()

    def join(self):
        self.tray_thread.join()
        self.worker_thread.join()
        if self.overlay is not None:
            self.overlay.join()
        if self.config_window is not None:
            self.config_window.join()  # let it save its settings before main.py writes them

    def stop(self):
        self.stop_event.set()  # closes the tray, the worker loop and the overlay

    def launch_config_window(self):
        """Show the configuration window. Does nothing if it's already open."""
        with self._windows_lock:
            if self.config_window is not None and self.config_window.is_alive():
                return
            self.config_window = ConfigurationWindow(self)
            self.config_window.start()

    def _update_overlay(self, show):
        if not show and self.overlay is not None:
            self.overlay.close()
            self.overlay = None # Delete Overlay
        elif show and self.overlay is None:
            self.overlay = OverlayWindow(self)
            self.overlay.start()  # a window only appears once started

    def _challenge_still_wanted(self) -> bool:
        """False once the user quits or turns challenges off. A round takes a while (Gemini,
        playback, recording), so it checks this between steps and stops early if so."""
        if self.stop_event.is_set():
            return False
        return config.get_config().getboolean('Challenge', 'is_active')

    # Retry n times until perfect
    def _compare_voice_input(self, target_lang: str, sent_phonetics: list[str], estimated_duration: float) -> FailSeverity:
        attempts = []

        for attempt_num in range(1, VOICE_INPUT_MAX_ATTEMPTS + 1):
            self.overlay.set_attempt(attempt_num, VOICE_INPUT_MAX_ATTEMPTS)
            print('recording voice')
            self.overlay.set_recording(True, estimated_duration)
            wav = recording.record(estimated_duration)
            self.overlay.set_recording(False)
            print('finished recording voice')

            if not self._challenge_still_wanted():  # turned off while recording: no score, no punishment
                return FailSeverity.PERFECT
            resp_phon = phon.generate(wav, target_lang)

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

    def _run_challenge(self):
        print('_run_challenge()')
        conf = config.get_config()

        s_ctx = sentence_context_factory(ContextKind.SCREEN_IMAGE)
        if s_ctx is None:
            return

        with ProcessingIndicator(self.overlay):
            # 1. Generate Sentence and phonetics
            print('Generating Sentence')
            self.overlay.set_processing(True)
            gen = self.generator.generate(s_ctx)
            self.overlay.set_processing(True)

        if not self._challenge_still_wanted():  # the Gemini call can take a few seconds
            return
        print('Sentence Generated')

        target_lang = conf['Language']['target']
        proficieny = conf['Language']['proficiency']

        self.overlay.set_language_label(target_lang, proficieny)  # new: fills the header
        self.overlay.set_source_lang_sentence(gen.source_lang)
        self.overlay.set_target_lang_sentence(gen.target_lang)

        print('Generating phonetics')
        sent_phon = phon.generate(gen.target_lang, target_lang)
        print('Phonetics generated')

        if conf.getboolean("Challenge", "playback"):
            print('Outputting playback')
            speaking.speak(sent_phon)
            if not self._challenge_still_wanted():  # don't start recording if they turned it off mid-playback
                return
            print('Finished outputting playback')

        est_dur = phon.speak_duration_estimate(sent_phon, proficieny)

        fail_severity = self._compare_voice_input(target_lang, sent_phon, est_dur)
        if not self._challenge_still_wanted(): return

        # Onlish punish if they actually deserve it
        if fail_severity > FailSeverity.CLOSE:
            pun = punishment_factory(fail_severity)
            pun.punish()

    # The main work being done by the worker thread
    def worker(self):
        prev_read_time = None

        """Worker loop: runs until the user clicks Quit in the tray."""
        while not self.stop_event.is_set():
            # TODO: poll / handle system events here
            print("checking for events...")

            conf = config.get_config()
            is_active = conf.getboolean('Challenge', 'is_active')
            if not is_active:
                self._update_overlay(False)
            else:
                self._update_overlay(True)

                # Run challenge logic
                now = time.perf_counter()
                if (prev_read_time is None) or (now - prev_read_time > CONTEXT_READ_DELAY):
                    self._run_challenge()
                    prev_read_time = now

            # Like sleep(1), but returns immediately when stop_event is set,
            # so Quit doesn't have to wait for the sleep to finish.
            self.stop_event.wait(1)

        print("worker shutting down")