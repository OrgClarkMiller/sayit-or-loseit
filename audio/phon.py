from functools import lru_cache
import numpy as np

from phonemizer.backend import EspeakBackend
from phonemizer.separator import Separator
from transformers import AutoModelForCTC, AutoProcessor
import torch

from languages import LANGUAGE_SHORT_FORM, LanguageProficiency, SECONDS_PER_PHONEME

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

RECORD_PADDING = 1.5        # reaction time before speaking + trailing silence

def init_lang(lang: str): _backend(LANGUAGE_SHORT_FORM[lang])

def init_model(): _model()

def generate(source: str | np.ndarray, target_language: str) -> list[str]:
    if isinstance(source, str): return _generate_from_sentence(source, target_language)
    elif isinstance(source, np.ndarray): return _generate_from_audio(source)
    raise ValueError('Invalid source type')

def speak_duration_estimate(phon: list[str], proficiency: str) -> float:
    return len(phon) * SECONDS_PER_PHONEME[proficiency] + RECORD_PADDING

def similarity(expected: list[str], actual: list[str]) -> float:
    """How close the phonemes heard were to the expected ones, as a percentage (0-100).

    e.g. similarity(['h', 'ə', 'l', 'oʊ'], ['h', 'ɛ', 'l', 'oʊ']) -> 80.0

    Compares symbol by symbol rather than phone by phone, so espeak and the recognizer
    splitting sounds differently ('ɑːɹ' vs 'ɑː', 'ɹ') isn't an error, and a near miss like
    'ɜ' for 'ɜː' only costs the missing length mark.
    """
    exp = "".join(expected)
    act = "".join(actual)
    if not exp:
        return 100.0 if not act else 0.0

    # 100% = identical; each edit needed to turn what was said into what was expected costs
    # 1/len(expected). Extra sounds count too, so long babble can't score well.
    return max(0.0, 1 - _edit_distance(exp, act) / len(exp)) * 100

def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance: fewest insertions, deletions and substitutions turning a into b."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,                 # delete ca
                           cur[j - 1] + 1,              # insert cb
                           prev[j - 1] + (ca != cb)))   # substitute (free if equal)
        prev = cur
    return prev[-1]

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
