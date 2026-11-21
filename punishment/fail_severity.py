from enum import Enum

import color_palette  # project root module; the app runs from the root, like `import config`


class FailSeverity(Enum):
    PERFECT = 1
    CLOSE   = 2
    MEDIUM  = 3
    MAJOR   = 4
    SEVERE  = 6


# Same scale as the overlay's similarity colors: green (spot on) through to red (way off)
FAIL_SEVERITY_COLOR = {
    FailSeverity.PERFECT: color_palette.GREEN,
    FailSeverity.CLOSE:   color_palette.LIME,
    FailSeverity.MEDIUM:  color_palette.AMBER,
    FailSeverity.MAJOR:   color_palette.ORANGE,
    FailSeverity.SEVERE:  color_palette.RED,
}

def get_fail_severity(similarity: float):
    if similarity < 15: return FailSeverity.SEVERE
    elif similarity < 30: return FailSeverity.MAJOR
    elif similarity < 50: return FailSeverity.MEDIUM
    elif similarity < 75: return FailSeverity.CLOSE
    else: return FailSeverity.PERFECT