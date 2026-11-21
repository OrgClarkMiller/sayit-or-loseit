from configparser import ConfigParser

_config: ConfigParser | None = None
CONF_PATH = "conf.ini"

def get_config():
    global _config

    if _config is None:
        _config = ConfigParser()
        _config.read(CONF_PATH)

    return _config

def save_config():
    global _config

    if _config is None: return
    with open(CONF_PATH, mode="w", encoding="utf-8") as confFile:
        _config.write(confFile)