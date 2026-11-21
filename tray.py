import threading
from pathlib import Path

import pystray
from PIL import Image

ICON_PATH = Path(__file__).parent / "assets" / "tray-icon.png"

class TrayManager:
    def __init__(self, worker_func):
        self.image = Image.open(ICON_PATH)
        self.menu = self.get_menu()
        self.worker_func = worker_func
        self.stop_event = threading.Event()
        
        self.icon = pystray.Icon(  
				name="say_it_lose_it",  # Internal name (not visible)  
				icon=self.image,          # Icon image  
				title="Say it or Lose it",  # Tooltip (shows on hover)  
				menu=self.menu            # Menu items  
			)
        
    def get_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Configuration", self.launch_config_window),
            pystray.MenuItem('Quit', self.on_quit)
        )
        
    def launch_config_window(self):
        print('Launch config window')
    
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