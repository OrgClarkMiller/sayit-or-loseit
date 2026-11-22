import threading
from tray import TrayManager
from window import ConfigurationWindow
from window.overlay import OverlayWindow
import config
from audio import phon
from challenge import ChallengeScheduler, SettingsStore

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

        # Windows run on their own threads (started by .start()) and close on stop_event.
        # Their public methods are thread-safe, e.g. ctx.overlay.render_state(...) from anywhere.
        self.overlay = None
        self._update_overlay(config.get_config().getboolean('Challenge', 'is_active')) # Show the overlay

        # The config window can be opened and closed repeatedly; a fresh one is made each time.
        self._windows_lock = threading.Lock()  # launches can come from the tray or worker thread
        self.config_window = None

        # Lambdas: the store and the scheduler each need the other, so each looks the
        # other up only when called
        self.settings = SettingsStore(get_overlay=lambda: self.overlay,
                                      on_ready=lambda: self.scheduler.wake())
        self.scheduler = ChallengeScheduler(self.stop_event, self.settings, self._update_overlay)
        self.worker_thread = threading.Thread(target=self.scheduler.run, daemon=True)

        self.apply_config()  # last: its on_ready needs self.scheduler

    def apply_config(self):
        """Rebuild the challenge settings from the current config. Call after changing it."""
        self.settings.apply_config()

    def on_change_challenge_status(self):
        print('on_change_challenge_status()')
        self.scheduler.run_now()  # make the challenge start right away

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
        self.scheduler.wake()  # the worker sleeps between passes, so wake it to see stop_event

    def launch_config_window(self):
        """Show the configuration window. Does nothing if it's already open."""
        with self._windows_lock:
            if self.config_window is not None and self.config_window.is_alive():
                return
            self.config_window = ConfigurationWindow(self)
            self.config_window.start()

    def _update_overlay(self, show: bool) -> OverlayWindow | None:
        """Create or close the overlay to match `show`. Returns the current one."""
        if not show and self.overlay is not None:
            self.overlay.close()
            self.overlay = None # Delete Overlay
        elif show and self.overlay is None:
            self.overlay = OverlayWindow(self)
            self.overlay.start()  # a window only appears once started
        return self.overlay
