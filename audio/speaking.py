from functools import lru_cache
from pathlib import Path
import threading

import numpy as np
from piper import PiperVoice
from languages import LANGUAGE_SHORT_FORM
import subprocess
import sys
import sounddevice as sd

# audio/ -> project root -> assets/voice-models
VOICE_MODEL_DIR_PATH = Path(__file__).parent.parent / "assets" / "voice-models"

# espeak code (LANGUAGE_SHORT_FORM) -> Piper voice model file. Each needs its .onnx.json next
# to it; get_voice_model() downloads missing ones on first use (about 60 MB each). By hand:
#   python -m piper.download_voices <name> --download-dir assets/voice-models
# All are espeak-phoneme voices, since speak() feeds them espeak phonemes from audio/phon.py.
# Voices list: https://huggingface.co/rhasspy/piper-voices/blob/main/voices.json
lang_model_name_dict = {
    'sq':    'sq_AL-edon-medium.onnx',
    'ar':    'ar_JO-kareem-medium.onnx',
    'hy':    'hy_AM-gor-medium.onnx',
    'eu':    'eu_ES-antton-medium.onnx',
    'bn':    'bn_BD-google-medium.onnx',
    'bg':    'bg_BG-dimitar-medium.onnx',
    'ca':    'ca_ES-upc_ona-medium.onnx',
    'cmn':   'zh_CN-huayan-medium.onnx',      # the espeak one: the newer zh voices use pinyin
    'cs':    'cs_CZ-jirka-medium.onnx',
    'da':    'da_DK-talesyntese-medium.onnx',
    'nl':    'nl_NL-mls-medium.onnx',
    'en-us': 'en_US-lessac-medium.onnx',
    'et':    'et_EE-news-medium.onnx',
    'fi':    'fi_FI-harri-medium.onnx',
    'fr-fr': 'fr_FR-siwis-medium.onnx',
    'ka':    'ka_GE-natia-medium.onnx',
    'de':    'de_DE-thorsten-medium.onnx',
    'el':    'el_GR-rapunzelina-medium.onnx',
    'hi':    'hi_IN-pratham-medium.onnx',
    'hu':    'hu_HU-anna-medium.onnx',
    'is':    'is_IS-bui-medium.onnx',
    'id':    'id_ID-news_tts-medium.onnx',
    'it':    'it_IT-paola-medium.onnx',
    'kk':    'kk_KZ-issai-high.onnx',
    'ko':    'ko_KR-kss-medium.onnx',
    'ku':    'ku_TR-berfin_renas-medium.onnx',
    'lv':    'lv_LV-aivars-medium.onnx',
    'lb':    'lb_LU-marylux-medium.onnx',
    'ml':    'ml_IN-arjun-medium.onnx',
    'mr':    'mr_IN-google-medium.onnx',
    'ne':    'ne_NP-chitwan-medium.onnx',
    'nb':    'no_NO-talesyntese-medium.onnx',
    'fa':    'fa_IR-amir-medium.onnx',
    'pl':    'pl_PL-gosia-medium.onnx',
    'pt-br': 'pt_BR-cadu-medium.onnx',
    'ro':    'ro_RO-mihai-medium.onnx',
    'ru':    'ru_RU-irina-medium.onnx',
    'sr':    'sr_RS-serbski_institut-medium.onnx',
    'sk':    'sk_SK-lili-medium.onnx',
    'sl':    'sl_SI-artur-medium.onnx',
    'es':    'es_ES-davefx-medium.onnx',
    'sw':    'sw_CD-lanfrica-medium.onnx',
    'sv':    'sv_SE-nst-medium.onnx',
    'te':    'te_IN-maya-medium.onnx',
    'tr':    'tr_TR-dfki-medium.onnx',
    'uk':    'uk_UA-tetiana-high.onnx',       # the espeak one: ukrainian_tts-medium reads raw text
    'ur':    'ur_PK-aegis_female-medium.onnx',
    'vi':    'vi_VN-vais1000-medium.onnx',
    'cy':    'cy_GB-gwryw_gogleddol-medium.onnx',
}

def download_voice_model(model_name: str):
    """Download a Piper voice (.onnx + .onnx.json) into VOICE_MODEL_DIR_PATH. Raises if it fails."""
    VOICE_MODEL_DIR_PATH.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "-m", "piper.download_voices",  # this venv's Python, not whatever "python" is on PATH
            "--download-dir", str(VOICE_MODEL_DIR_PATH),
            model_name.removesuffix(".onnx"),  # it takes the voice name, e.g. en_US-lessac-medium
        ],
        check=True,
    )

# Check if file exists, if it doesn't download it first
def get_voice_model(lang: str):
    lang_key = LANGUAGE_SHORT_FORM[lang]
    model_name = lang_model_name_dict[lang_key]
    voice_model_path = VOICE_MODEL_DIR_PATH / model_name
    if not voice_model_path.exists():
        download_voice_model(model_name)

    return PiperVoice.load(voice_model_path)

_voice_lock = threading.Lock()

@lru_cache(maxsize=None)
def _cached_voice(lang: str) -> PiperVoice:
    return get_voice_model(lang)

def get_voice(lang: str) -> PiperVoice:
    """The voice for a language, loaded (and downloaded if needed) on first use.

    No module-level "current voice": callers hold the voice they're using, so switching
    language on another thread can't swap it out halfway through speak(). The lock stops
    two threads loading (or downloading) the same voice at once.
    """
    with _voice_lock:
        return _cached_voice(lang)

def _to_piper_phonemes(phonetics: list[str], voice: PiperVoice) -> list[str]:
    """['b', 'ɔ̃', 'ʒ', 'u', 'ʁ'] -> ['b', 'ɔ', '̃', 'ʒ', 'u', 'ʁ', '.']

    Piper's ids are per character, so multi-character phones ('oʊ', 'ɜː', 'ɔ̃') are split
    into their code points. The closing '.' gives the sentence a falling end.
    Anything the voice doesn't know is dropped.
    """
    known = voice.config.phoneme_id_map
    chars = [c for phone in phonetics for c in phone if c in known]
    chars.append(".")
    return chars


def synthesize(phonetics: list[str], voice: PiperVoice) -> np.ndarray:
    """Phonemes (as built by phon.generate) -> float32 audio at voice.config.sample_rate."""
    ids = voice.phonemes_to_ids(_to_piper_phonemes(phonetics, voice))
    return np.asarray(voice.phoneme_ids_to_audio(ids), dtype=np.float32)

def speak(phonetics: list[str], voice: PiperVoice):
    """Play phonemes through the speakers with the given voice. Blocks until playback finishes."""
    sd.play(synthesize(phonetics, voice), samplerate=voice.config.sample_rate)
    sd.wait()
