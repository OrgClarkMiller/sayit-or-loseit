from .punishment import Punishment, FailSeverity, PunishAction
import mouse
import keyboard
import random
import time

MAX_FLICK = 100
MIN_FLICK = 25

MAX_JUMPS = 8
MIN_JUMPS = 3

MIN_WASTE_DUR = 10
MAX_WASTE_DUR = 30

FPS_NAMES = set(['csgo', 'beanbattles'])
def is_fps(window_name_split: list[str]):
    for s in window_name_split:
        if s in FPS_NAMES: return True
    return False

class WasteAmmo(PunishAction):
    def __init__(self):
        super().__init__('Waste your bullets')

    def punish(self):
        dur = random.randint(MIN_WASTE_DUR, MAX_WASTE_DUR)
        # Click dur times, so maybe shoot like 20 times, around there :)
        for _ in range(dur):
            mouse.click()

class MouseFlickPunishAction(PunishAction):
    def __init__(self):
        super().__init__("Mouse Flick")

    def punish(self):
        from_x, from_y = mouse.get_position()

        x_diff = random.randint(MIN_FLICK, MAX_FLICK)
        y_diff = random.randint(MIN_FLICK, MAX_FLICK)

        # Update mouses position to dragged in random direction
        mouse.drag(from_x, from_y, from_x + x_diff, from_y + y_diff, absolute=False, duration=0.1)

class JumpPunishAction(PunishAction):
    def __init__(self):
        super().__init__("Leap Frog")

    def punish(self):
        jump_count = random.randint(MIN_JUMPS, MAX_JUMPS)

        for _ in range(jump_count): # Must be even for unpause event
            keyboard.press_and_release("space")
            time.sleep(1)

def _get_action(severity: FailSeverity):
    match severity:
        case FailSeverity.SEVERE: return WasteAmmo()
        case FailSeverity.MAJOR: return JumpPunishAction()
        case FailSeverity.MEDIUM: return random.choice([MouseFlickPunishAction()]) # Do a random action, TODO: DO ANOTHER ACTION
    raise ValueError(f"No media punishment for severity {severity.name}")

class FPSPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity)
        self.action = _get_action(self.severity)

    def get_punishment_name(self): return self.action.get_name()
    def punish(self): return self.action.punish()
