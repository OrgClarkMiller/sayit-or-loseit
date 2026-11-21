import threading
from pathlib import Path

import pystray
from PIL import Image

from configuration_window import ConfigurationWindow

ICON_PATH = Path(__file__).parent / "assets" / "tray-icon.png"

class TrayManager:
    def __init__(self, worker_func):
        self.image = Image.open(ICON_PATH)
        self.menu = self.get_menu()
        self.worker_func = worker_func
        self.stop_event = threading.Event()
        self.window_thread = None

        self.icon = pystray.Icon(
            name="say_it_lose_it",       # Internal name (not visible)
            icon=self.image,             # Icon image
            title="Say it or Lose it",   # Tooltip (shows on hover)
            menu=self.menu,              # Menu items
        )

    def get_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Configuration", self.launch_config_window),
            pystray.MenuItem('Quit', self.on_quit)
        )

    def launch_config_window(self):
        if (self.window_thread is not None): return # Can't open more than one window_thread

        def lnch_worker():
            try:
                ConfigurationWindow()  # mainloop() blocks this thread until the window closes
            finally:
                self.window_thread = None  # runs even if the window crashes

        print('Launching config window')
        # mainloop() blocks, so run the window on its own thread to keep the tray responsive.
        # daemon=True lets the process exit on Quit even if the window is still open.
        self.window_thread = threading.Thread(target=lnch_worker, daemon=True)
        self.window_thread.start()

    def on_quit(self):
        """Signal the worker to stop, then stop the tray icon."""
        self.stop_event.set()
        self.icon.stop()

    def _setup(self, icon):
        # pystray runs this in its own thread once the icon is ready.
        # Passing setup hides the icon by default, so show it explicitly.
        icon.visible = True
        self.worker_func(self.stop_event)

    def run(self):
        self.icon.run(setup=self._setup)