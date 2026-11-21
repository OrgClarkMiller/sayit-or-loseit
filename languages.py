from enum import StrEnum

LANGUAGES = [
    'English',
    'French',
    'Spanish',
    'Dutch',
    'Polish'
]

# espeak-ng language codes, as accepted by phonemizer's espeak backend
LANGUAGE_SHORT_FORM = {
    'English': 'en-us',
    'French': 'fr-fr',
    'Spanish': 'es',
    'Dutch': 'nl',
    'Polish': 'pl'
}

class LanguageProficiency(StrEnum):
    """Proficiency levels, lowest to highest: a beginner level, then the CEFR levels."""
    FRESHY = "< A1" # You know like nothing
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

# How long a speaker at each level takes per phoneme. Natives are ~0.08; these are starting guesses to tune.
SECONDS_PER_PHONEME: dict[LanguageProficiency, float] = {
    LanguageProficiency.FRESHY: 0.20,
    LanguageProficiency.A1:     0.18,
    LanguageProficiency.A2:     0.16,
    LanguageProficiency.B1:     0.14,
    LanguageProficiency.B2:     0.12,
    LanguageProficiency.C1:     0.10,
    LanguageProficiency.C2:     0.09,
}