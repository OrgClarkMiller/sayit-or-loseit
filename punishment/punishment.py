from abc import ABC, abstractmethod
from .fail_severity import FailSeverity

class Punishment(ABC):
    def __init__(self, fail_severity: FailSeverity):
        self.severity = fail_severity

    @abstractmethod
    def get_punishment_name(self) -> str:
        pass

    @abstractmethod
    def punish(self):
        pass