from .media_punishment import MediaPunishment

def punishment_factory(process_name: str, fail_severity: str) -> MediaPunishment:
    # TODO: Properly determine punishment class
    return MediaPunishment(fail_severity)