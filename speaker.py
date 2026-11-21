import numpy as np
import sounddevice as sd
from piper import PiperVoice

voice = PiperVoice.load("fr_FR-siwis-medium.onnx")


def _to_piper_phonemes(phonetics: list[list[str]]) -> list[str]:
    """[['b', 'ɔ̃'], ['ʒ', 'u', 'ʁ']] -> ['b', 'ɔ', '̃', ' ', 'ʒ', 'u', 'ʁ', '.']

    Piper's ids are per character, so multi-character phones ('oʊ', 'ɜː', 'ɔ̃') are split
    into their code points. Words are separated by spaces, and the closing '.' gives the
    sentence a falling end. Anything the voice doesn't know is dropped.
    """
    known = voice.config.phoneme_id_map
    chars: list[str] = []
    for i, word in enumerate(phonetics):
        if i > 0:
            chars.append(" ")
        chars.extend(c for phone in word for c in phone if c in known)
    chars.append(".")
    return chars


def synthesize(phonetics: list[list[str]]) -> np.ndarray:
    """Phonemes (as built by phon.generate) -> float32 audio at voice.config.sample_rate."""
    ids = voice.phonemes_to_ids(_to_piper_phonemes(phonetics))
    return np.asarray(voice.phoneme_ids_to_audio(ids), dtype=np.float32)

def speak(phonetics: list[list[str]]):
    """Play phonemes through the speakers. Blocks until playback finishes."""
    sd.play(synthesize(phonetics), samplerate=voice.config.sample_rate)
    sd.wait()
