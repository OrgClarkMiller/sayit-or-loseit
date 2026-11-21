# from pyinterceptor import Interception
from .punishment import Punishment

# interception = Interception()

class MediaPunishment(Punishment):
    def __init__(self, fail_severity):
        super().__init__(fail_severity, 5) # TODO: DETERMINE DURATION BASED OFF SEVERITY

    def punish(self):
        # Press spacebar, lock space bar for full duration
        def inp_cb(stroke):
            pass

        print(f'Carrying {self.severity} punishment for {self.duration}')