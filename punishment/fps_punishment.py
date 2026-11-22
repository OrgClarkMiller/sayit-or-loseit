from .punishment import Punishment, FailSeverity, PunishAction
import mouse
import random

MAX_FLICK = 100
MIN_FLICK = 25

FPS_NAMES = set(['csgo', 'beanbattles'])
def is_fps(window_name_split: list[str]):
    for s in window_name_split:
        if s in FPS_NAMES: return True
    return False

class MouseFlickPunishAction(PunishAction):
    def __init__(self):
        super().__init__('Mouse Flick')

    def punish(self):
        from_x, from_y = mouse.get_position()

        x_diff = random.randint(MIN_FLICK, MAX_FLICK)
        y_diff = random.randint(MIN_FLICK, MAX_FLICK)

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
