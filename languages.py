from enum import StrEnum

# espeak-ng language codes, as accepted by phonemizer's espeak backend, and each the espeak
# voice its Piper model was trained with (see audio/speaking.py).
#
# Only languages written in the Latin alphabet (accents are fine, e.g. Polish,
# Czech), so the sentence can be read off the overlay without learning a new script.
# Also needs a Piper voice trained on espeak phonemes, which rules out Lithuanian, and
# one clear enough that saying the sentence perfectly scores a pass (50%+ with
# phon.similarity), which rules out Danish (47%) and Vietnamese (28%, tonal).
LANGUAGE_SHORT_FORM = {
    'Albanian':           'sq',
    'Basque':             'eu',
    'Catalan':            'ca',
    'Czech':              'cs',
    'Dutch':              'nl',
    'English':            'en-us',
    'Estonian':           'et',
    'Finnish':            'fi',
    'French':             'fr-fr',
    'German':             'de',
    'Hungarian':          'hu',
    'Icelandic':          'is',
    'Indonesian':         'id',
    'Italian':            'it',
    'Kurdish (Kurmanji)': 'ku',
    'Latvian':            'lv',
    'Luxembourgish':      'lb',
    'Norwegian':          'nb',
    'Polish':             'pl',
    'Portuguese':         'pt-br',  # Brazilian
    'Romanian':           'ro',
    'Slovak':             'sk',
    'Slovenian':          'sl',
    'Spanish':            'es',
    'Swahili':            'sw',
    'Swedish':            'sv',
    'Turkish':            'tr',
    'Welsh':              'cy',
}

LANGUAGES = list(LANGUAGE_SHORT_FORM)  # the names, for the settings dropdowns

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