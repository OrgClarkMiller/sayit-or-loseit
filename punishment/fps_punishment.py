from .punishment import Punishment, FailSeverity, PunishAction
import mouse
import random

class MouseFlickPunishAction(PunishAction):
    def __init__(self):
        super().__init__('Mouse Flick')

    def punish(self):
        from_x, from_y = mouse.get_position()

        x_diff = random.randint(0, 25)
        y_diff = random.randint(0, 25)

        # Update mouses position to dragged in random direction
        mouse.drag(from_x, from_y, from_x + x_diff, from_y + y_diff, absolute=False, duration=0.1)

# TODO: FINISH ACTIONS
def _get_action(severity: FailSeverity):
    match severity:
        case FailSeverity.SEVERE: return MouseFlickPunishAction()
        case FailSeverity.MAJOR: return MouseFlickPunishAction()
        case FailSeverity.MEDIUM: return MouseFlickPunishAction()
    raise ValueError(f"No media punishment for severity {severity.name}")

class FPSPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity)
        self.action = _get_action(self.severity)

    def get_punishment_name(self): return self.action.get_name()
    def punish(self): return self.action.punish()
