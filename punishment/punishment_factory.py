from .fail_severity import FailSeverity
from .media_punishment import MediaPunishment

def punishment_factory(process_name: str, fail_severity: FailSeverity) -> MediaPunishment:
    # TODO: Properly determine punishment class
    return MediaPunishment(fail_severity)