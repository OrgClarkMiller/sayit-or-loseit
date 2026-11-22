from enum import StrEnum

# espeak-ng language codes, as accepted by phonemizer's espeak backend. Only languages
# with a Piper voice trained on espeak phonemes (see audio/speaking.py), and each code is
# the espeak voice that Piper model was trained with. Left out for having no such voice:
# Hebrew, Japanese, Lithuanian and Thai (their Piper voices use other phonemizers).
LANGUAGE_SHORT_FORM = {
    'Albanian':           'sq',
    'Arabic':             'ar',
    'Armenian':           'hy',
    'Basque':             'eu',
    'Bengali':            'bn',
    'Bulgarian':          'bg',
    'Catalan':            'ca',
    'Chinese (Mandarin)': 'cmn',
    'Czech':              'cs',
    'Danish':             'da',
    'Dutch':              'nl',
    'English':            'en-us',
    'Estonian':           'et',
    'Finnish':            'fi',
    'French':             'fr-fr',
    'Georgian':           'ka',
    'German':             'de',
    'Greek':              'el',
    'Hindi':              'hi',
    'Hungarian':          'hu',
    'Icelandic':          'is',
    'Indonesian':         'id',
    'Italian':            'it',
    'Kazakh':             'kk',
    'Korean':             'ko',
    'Kurdish (Kurmanji)': 'ku',
    'Latvian':            'lv',
    'Luxembourgish':      'lb',
    'Malayalam':          'ml',
    'Marathi':            'mr',
    'Nepali':             'ne',
    'Norwegian':          'nb',
    'Persian':            'fa',
    'Polish':             'pl',
    'Portuguese':         'pt-br',  # Brazilian
    'Romanian':           'ro',
    'Russian':            'ru',
    'Serbian':            'sr',
    'Slovak':             'sk',
    'Slovenian':          'sl',
    'Spanish':            'es',
    'Swahili':            'sw',
    'Swedish':            'sv',
    'Telugu':             'te',
    'Turkish':            'tr',
    'Ukrainian':          'uk',
    'Urdu':               'ur',
    'Vietnamese':         'vi',
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