from functools import lru_cache
import numpy as np

from phonemizer.backend import EspeakBackend
from phonemizer.separator import Separator
from transformers import AutoModelForCTC, AutoProcessor
import torch

from languages import LANGUAGE_SHORT_FORM

_WORD_SEP = "|"
_SEPARATOR = Separator(phone=" ", word=_WORD_SEP)

MODEL_ID = "facebook/wav2vec2-lv-60-espeak-cv-ft"
SAMPLE_RATE = 16_000  # the model only understands 16 kHz mono audio

@lru_cache(maxsize=None)
def _backend(lng_short: str) -> EspeakBackend:
    # Starting espeak is slow, so keep one backend per language.
    # No stress marks: phoneme recognition models (wav2vec2 espeak) don't output them,
    # and they'd show up as mismatches when comparing.
    return EspeakBackend(lng_short, preserve_punctuation=False, with_stress=False)

@lru_cache(maxsize=1)
def _model():
    # Slow to load (~1.2 GB download on first run), so do it once
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForCTC.from_pretrained(MODEL_ID).eval()
    return processor, model

def init_lang(lang: str): _backend(LANGUAGE_SHORT_FORM[lang])

def init_model(): _model()

def _flatten(word_phonemes: list[list[str]]) -> list[str]:
    return [p for word in word_phonemes for p in word]

def _generate_from_sentence(sentence: str, target_language: str) -> list[str]:
    # Throws if unsupported language is entered
    lng_short = LANGUAGE_SHORT_FORM[target_language]

    phonemized = _backend(lng_short).phonemize([sentence], separator=_SEPARATOR, strip=True)[0]

    res = [word.split() for word in phonemized.split(_WORD_SEP) if word.strip()]
    return _flatten(res)

def _generate_from_audio(audio: np.ndarray) -> list[str]:
    """16 kHz mono float32 audio -> phonemes heard, e.g. ['h', 'ə', 'l', 'oʊ', 'w', 'ɜː', 'l', 'd']"""
    processor, model = _model()
    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    with torch.no_grad():
        logits = model(inputs.input_values).logits
    ids = torch.argmax(logits, dim=-1)
    return processor.batch_decode(ids)[0].split()

def generate(source: str | np.ndarray, target_language: str) -> list[str]:
    if isinstance(source, str): return _generate_from_sentence(source, target_language)
    elif isinstance(source, np.ndarray): return _generate_from_audio(source)
    raise ValueError('Invalid source type')
