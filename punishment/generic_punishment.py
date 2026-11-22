import ctypes
from pathlib import Path

from .punishment import Punishment, FailSeverity, PunishAction
from playsound import playsound
import time
import mouse
import random

ROOT_DIR = Path(__file__).parent.parent
AUDIO_DIR = ROOT_DIR / "assets" / "audio"

AIRHORN_PATH  = AUDIO_DIR / "airhorn.mp3"

class AirhornPunishAction(PunishAction):
    def __init__(self):
        super().__init__('Airhorn')

    def punish(self):
        playsound(str(AIRHORN_PATH))

class SwapMouseButtonsPunishAction(PunishAction):
    def __init__(self, seconds: float = 10):
        super().__init__('Swapped Mouse Buttons')
        self.seconds = seconds

    def punish(self):
        user32 = ctypes.windll.user32
        user32.SwapMouseButton(True)
        try:
            time.sleep(self.seconds)
        finally:
            user32.SwapMouseButton(False)  # always restore, even if something throws

class ShakyCursorPunishAction(PunishAction):
    def __init__(self, seconds: float = 3):
        super().__init__('Shaky Hands')
        self.seconds = seconds

    def punish(self):
        end = time.monotonic() + self.seconds
        while time.monotonic() < end:
            mouse.move(random.randint(-15, 15), random.randint(-15, 15), absolute=False)
            time.sleep(0.03)

def _get_action(severity: FailSeverity):
    match severity:
        case FailSeverity.SEVERE: return AirhornPunishAction()
        case FailSeverity.MAJOR: return SwapMouseButtonsPunishAction()
        case FailSeverity.MEDIUM: return ShakyCursorPunishAction()
    raise ValueError(f"No media punishment for severity {severity.name}")

class GenericPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity)
        self.action = _get_action(self.severity)

    def get_punishment_name(self): return self.action.get_name()
    def punish(self): return self.action.punish()
