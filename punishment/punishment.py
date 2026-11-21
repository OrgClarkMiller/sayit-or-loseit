from abc import ABC, abstractmethod
from .fail_severity import FailSeverity

class Punishment(ABC):
    def __init__(self, fail_severity: FailSeverity, duration: float):
        self.severity = fail_severity
        self.duration = duration

    @abstractmethod
    def punish(self):
        pass