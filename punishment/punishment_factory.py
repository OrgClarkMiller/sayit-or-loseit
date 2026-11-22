from .fail_severity import FailSeverity
from .media_punishment import MediaPunishment
from .fps_punishment import FPSPunishment
from .punishment import Punishment
# Absolute: punishment is a top-level package, so ".." has nowhere to go. And from the
# submodule, not the window package: window/__init__ imports overlay_window, which imports
# punishment, so "from window import ..." would hit a half-loaded window package.
from window.window_helpers import get_focused_details

FPS_NAMES = set(['csgo'])
MEDIA_NAMES = set(['youtube', 'netflix', 'disneyplus', 'anime', 'cartoon', 'wcofun'])

def is_media(window_name_split: list[str]):
    for s in window_name_split:
        if s in MEDIA_NAMES: return True
    return False

def is_fps(window_name_split: list[str]):
    for s in window_name_split:
        if s in FPS_NAMES: return True
    return False

def punishment_factory(fail_severity: FailSeverity) -> Punishment:
    wnd_dets = get_focused_details()

    # Split up the window title into an array of lowercase strings
    wnd_name_splt = [s.lower() for s in wnd_dets.title.split(' ')]

    print(f"Creating punishment for {wnd_dets.title}")

    if is_media(wnd_name_splt):
        return MediaPunishment(fail_severity)
    if is_fps(wnd_name_splt):
        return FPSPunishment(fail_severity)