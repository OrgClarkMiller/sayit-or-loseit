from enum import StrEnum

LANGUAGES = [
    'English',
    'French',
    'Spanish',
    'Dutch',
    'Polish'
]

class LanguageProficiency(StrEnum):
    """Proficiency levels, lowest to highest: a beginner level, then the CEFR levels."""
    FRESHY = "< A1" # You know like nothing
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
