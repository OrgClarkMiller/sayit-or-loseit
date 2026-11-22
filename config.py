from configparser import ConfigParser

from languages import LanguageProficiency

_config: ConfigParser | None = None
CONF_PATH = "conf.ini"

# Every setting the app reads, with its value for a fresh install. Values are strings
# because that's all configparser stores.
DEFAULTS: dict[str, dict[str, str]] = {
    "Language": {
        "source": "English",
        "target": "French",
        "proficiency": LanguageProficiency.FRESHY.value,
    },
    "Sentence": {
        "max_words": "15",
    },
    "AI": {
        "gemini_key": "",
    },
    "Challenge": {
        "is_active": "False",  # off until the user has entered a Gemini key and turned it on
        "playback": "True",
    },
}

def set_defaults():
    """Fill in any section or setting missing from the config. Never overwrites a value
    the user has set, so it's safe to run on every load."""
    for section, values in DEFAULTS.items():
        if not _config.has_section(section):
            _config.add_section(section)
        for key, value in values.items():
            if not _config.has_option(section, key):
                _config.set(section, key, value)

def get_config():
    global _config

    if _config is None:
        _config = ConfigParser()
        _config.read(CONF_PATH)
        set_defaults()

    return _config

def save_config():
    global _config

    if _config is None: return
    with open(CONF_PATH, mode="w", encoding="utf-8") as confFile:
        _config.write(confFile)