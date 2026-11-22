"""What happens when the user fails a challenge, scaled by how badly they failed."""
from .fail_severity import FAIL_SEVERITY_COLOR, FailSeverity, get_fail_severity
from .punishment import Punishment
from .media_punishment import MediaPunishment
from .punishment_factory import punishment_factory

__all__ = [
    "FAIL_SEVERITY_COLOR",
    "FailSeverity",
    "get_fail_severity",
    "Punishment",
    "MediaPunishment",
    "punishment_factory",
]
