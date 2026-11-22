import keyboard
from .punishment import Punishment, FailSeverity, PunishAction
import time

class SpamSpacePunishAction(PunishAction):
    def __init__(self):
        super().__init__('Rapid Media Pause')

    def punish(self):
        for _ in range(4): # Must be even for unpause event
            keyboard.press_and_release("space")
            time.sleep(1)

class CloseMediaPunishAction(PunishAction):
    def __init__(self):
        super().__init__('Close Media')

    def punish(self):
        keyboard.send('ctrl+w') # Closes browser tab

def _get_action(severity: FailSeverity):
    match severity:
        case FailSeverity.SEVERE: return CloseMediaPunishAction()
        case FailSeverity.MAJOR: return SpamSpacePunishAction()
        case FailSeverity.MEDIUM: return SpamSpacePunishAction()
    raise ValueError(f"No media punishment for severity {severity.name}")

class MediaPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity)
        self.action = _get_action(self.severity)

    def get_punishment_name(self): return self.action.get_name()

    def punish(self): return self.action.punish()
