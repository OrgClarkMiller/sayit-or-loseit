from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pystray
from PIL import Image

if TYPE_CHECKING:  # type hints only; a real import would be circular (app_context imports tray)
    from app_context import AppContext

ICON_PATH = Path(__file__).parent / "assets" / "tray-icon.png"

class TrayManager:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.image = Image.open(ICON_PATH)
        self.menu = self.get_menu()

        self.icon = pystray.Icon(
            name="say_it_lose_it",       # Internal name (not visible)
            icon=self.image,             # Icon image
            title="Say it or Lose it",   # Tooltip (shows on hover)
            menu=self.menu,              # Menu items
        )

    def get_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Configuration", self.ctx.launch_config_window),
            pystray.MenuItem('Quit', self.on_quit)
        )

    def on_quit(self):
        """Ask the whole app to stop; _setup sees the event and stops the icon."""
        self.ctx.stop()

    def _setup(self, icon):
        # pystray runs this in its own thread once the icon is ready.
        # Passing setup hides the icon by default, so show it explicitly.
        icon.visible = True

        # Block this setup thread until anyone (Quit, another window, the worker)
        # calls ctx.stop(), then shut the tray down. icon.stop() makes run() return.
        self.ctx.stop_event.wait()
        icon.stop()

    def run(self):
        self.icon.run(setup=self._setup)