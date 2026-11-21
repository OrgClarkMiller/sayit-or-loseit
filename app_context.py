import threading
from tray import TrayManager
from overlay_window import OverlayWindow
from configuration_window import ConfigurationWindow

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
        self.overlay = OverlayWindow(self.stop_event)  # open for the app's whole lifetime

        # The config window can be opened and closed repeatedly; a fresh one is made each time.
        self._windows_lock = threading.Lock()  # launches can come from the tray or worker thread
        self.config_window = None

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

    # The main work being done by the worker thread
    def worker(self):
        pass

    def launch_config_window(self):
        """Show the configuration window. Does nothing if it's already open."""
        with self._windows_lock:
            if self.config_window is not None and self.config_window.is_alive():
                return
            self.config_window = ConfigurationWindow(self.stop_event)
            self.config_window.start()
