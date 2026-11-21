from pathlib import Path

import numpy as np
from piper import PiperVoice
from languages import LANGUAGE_SHORT_FORM
import subprocess
import sys

print('Importing sounddevice')
import sounddevice as sd
print('Finished importing sounddevice')

voice: PiperVoice | None

DEFAULT_LANG = 'English'

# audio/ -> project root -> assets/voice-models
VOICE_MODEL_DIR_PATH = Path(__file__).parent.parent / "assets" / "voice-models"

# espeak code (LANGUAGE_SHORT_FORM) -> Piper voice model file. Each needs its .onnx.json next to it.
# Download missing ones with: python -m piper.download_voices <name> --download-dir assets/voice-models
lang_model_name_dict = {
    'en-us': 'en_US-lessac-medium.onnx',
    'fr-fr': 'fr_FR-siwis-medium.onnx',
    'es':    'es_ES-davefx-medium.onnx',   # not downloaded yet
    'nl':    'nl_NL-mls-medium.onnx',      # not downloaded yet
    'pl':    'pl_PL-gosia-medium.onnx',    # not downloaded yet
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

def load_voice(lang: str = DEFAULT_LANG):
    global voice
    voice = get_voice_model(lang)

def _to_piper_phonemes(phonetics: list[str]) -> list[str]:
    """['b', 'ɔ̃', 'ʒ', 'u', 'ʁ'] -> ['b', 'ɔ', '̃', 'ʒ', 'u', 'ʁ', '.']

    Piper's ids are per character, so multi-character phones ('oʊ', 'ɜː', 'ɔ̃') are split
    into their code points. The closing '.' gives the sentence a falling end.
    Anything the voice doesn't know is dropped.
    """
    known = voice.config.phoneme_id_map
    chars = [c for phone in phonetics for c in phone if c in known]
    chars.append(".")
    return chars


def synthesize(phonetics: list[str]) -> np.ndarray:
    """Phonemes (as built by phon.generate) -> float32 audio at voice.config.sample_rate."""
    ids = voice.phonemes_to_ids(_to_piper_phonemes(phonetics))
    return np.asarray(voice.phoneme_ids_to_audio(ids), dtype=np.float32)

def speak(phonetics: list[str]):
    """Play phonemes through the speakers. Blocks until playback finishes."""
    sd.play(synthesize(phonetics), samplerate=voice.config.sample_rate)
    sd.wait()
