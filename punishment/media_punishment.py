import keyboard
from .punishment import Punishment
import time

class MediaPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity, 5) # TODO: DETERMINE DURATION BASED OFF SEVERITY

    def punish(self):
        print(f'Carrying {self.severity} punishment for {self.duration}')

        # Spam spacebar to make playback difficult for the duration
        for i in range(4): # Must be even for unpause event
            keyboard.press_and_release("space")
            time.sleep(1)

        # Sleep for 5 seconds
        # time.sleep(5)