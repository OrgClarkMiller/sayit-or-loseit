from pathlib import Path

from .punishment import Punishment, FailSeverity, PunishAction
from playsound import playsound

ROOT_DIR = Path(__file__).parent.parent
AUDIO_DIR = ROOT_DIR / "assets" / "audio"

AIRHORN_PATH  = AUDIO_DIR / "airhorn.mp3"

class AirhornPunishAction(PunishAction):
    def __init__(self):
        super().__init__('Airhorn')

    def punish(self):
        #TODO: Store old volume val, set to max, restor to old volume val
        playsound(str(AIRHORN_PATH))

# TODO: FINISH ACTIONS
def _get_action(severity: FailSeverity):
    match severity:
        case FailSeverity.SEVERE: return AirhornPunishAction()
        case FailSeverity.MAJOR: return AirhornPunishAction()
        case FailSeverity.MEDIUM: return AirhornPunishAction()
    raise ValueError(f"No media punishment for severity {severity.name}")

class GenericPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity)
        self.action = _get_action(self.severity)

    def get_punishment_name(self): return self.action.get_name()
    def punish(self): return self.action.punish()
