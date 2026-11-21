import threading
from languages import LanguageProficiency
from sentence_generator import SentenceGenerator
from tray import TrayManager
from overlay_window import OverlayWindow
from configuration_window import ConfigurationWindow
import config
from sentence_context_factory import sentence_context_factory, ContextKind
import time

# Holds refs to all essential components such as
#the tray, the different windows and things
#like stop events to make all windows and such
#close out properly

CONTEXT_READ_DELAY = 15

# Mediator Class (child components talk to this to do things like program shutdown)
class AppContext:
    def __init__(self):
        self.stop_event = threading.Event()
        self.tray = TrayManager(self)
        self.tray_thread = threading.Thread(target=self.tray.run, daemon=True)
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)

        # Windows run on their own threads (started by .start()) and close on stop_event.
        # Their public methods are thread-safe, e.g. ctx.overlay.set_text("hi") from anywhere.
        self.overlay = OverlayWindow(self.stop_event)  # open for the app's whole lifetime

        # The config window can be opened and closed repeatedly; a fresh one is made each time.
        self._windows_lock = threading.Lock()  # launches can come from the tray or worker thread
        self.config_window = None

        conf = config.get_config()
        self.generator = SentenceGenerator(
            target_lang=conf.get("Language", "target", fallback="Russian"),
            proficiency=conf.get("Language", "proficiency", fallback=LanguageProficiency.FRESHY),
            max_words=conf.getint("Sentence", "max_words", fallback=10),
            gemini_api_key=conf["AI"]["gemini_key"]
        )

    def start(self):
        self.overlay.start()
        self.tray_thread.start()
        self.worker_thread.start()

    def join(self):
        self.tray_thread.join()
        self.worker_thread.join()
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
            self.config_window = ConfigurationWindow(self.stop_event)
            self.config_window.start()

    # Output sentence in target language to overlay window
    def _output_sentence(self):
        s_ctx = sentence_context_factory(ContextKind.SCREEN_TEXT)
        sentence = self.generator.generate(s_ctx)
        self.overlay.set_text(sentence)

        # TODO: Handle mic input, compare against sentence audio file


    # The main work being done by the worker thread
    def worker(self):
        # Handle reading the microphone, processing the context to build sentences, etc...# s_ctx = sentence_context_factory(ContextKind.SCREEN_TEXT)

        prev_read_time = time.perf_counter()

        """Worker loop: runs until the user clicks Quit in the tray."""
        while not self.stop_event.is_set():
            # TODO: poll / handle system events here
            print("checking for events...")

            now = time.perf_counter()
            if now - prev_read_time > CONTEXT_READ_DELAY:
                self._output_sentence()
            # Like sleep(1), but returns immediately when stop_event is set,
            # so Quit doesn't have to wait for the sleep to finish.
            self.stop_event.wait(1)

        print("worker shutting down")