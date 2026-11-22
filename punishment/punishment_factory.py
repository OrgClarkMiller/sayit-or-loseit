from .fail_severity import FailSeverity
from .media_punishment import MediaPunishment
from .punishment import Punishment
# Absolute: punishment is a top-level package, so ".." has nowhere to go. And from the
# submodule, not the window package: window/__init__ imports overlay_window, which imports
# punishment, so "from window import ..." would hit a half-loaded window package.
from window.window_helpers import get_focused_details

MEDIA_NAMES = set(['youtube', 'netflix', 'disneyplus'])

def is_media(window_name_split: list[str]):
    for s in window_name_split:
        if s in MEDIA_NAMES: return True
    return False


def punishment_factory(fail_severity: FailSeverity) -> Punishment:
    wnd_dets = get_focused_details()

    # Split up the window title into an array of lowercase strings
    wnd_name_splt = [s.lower() for s in wnd_dets.title.split(' ')]

    print(f"Creating punishment for {wnd_dets.title}")

    if is_media(wnd_name_splt):
        return MediaPunishment(fail_severity)