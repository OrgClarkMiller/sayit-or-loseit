from functools import lru_cache
import json
from pathlib import Path
import threading

import numpy as np
import onnxruntime as ort
from phonemizer.backend import EspeakBackend
from phonemizer.separator import Separator

from languages import LANGUAGE_SHORT_FORM, LanguageProficiency, SECONDS_PER_PHONEME

_WORD_SEP = "|"
_SEPARATOR = Separator(phone=" ", word=_WORD_SEP)

# facebook/wav2vec2-lv-60-espeak-cv-ft, exported to ONNX. Run with onnxruntime (already a
# Piper dependency) instead of torch + transformers, which took ~20 s just to import.
MODEL_REPO = "onnx-community/wav2vec2-lv-60-espeak-cv-ft-ONNX"
MODEL_FILE = "onnx/model.onnx"  # full precision: int8 was slower on CPU and misheard sounds
VOCAB_FILE = "vocab.json"
MODEL_DIR = Path(__file__).parent.parent / "assets" / "phoneme-model"  # audio/ -> project root
SAMPLE_RATE = 16_000  # the model only understands 16 kHz mono audio
_SPECIAL_TOKENS = {"<pad>", "<s>", "</s>", "<unk>"}

# espeak isn't thread-safe, and lru_cache doesn't lock while it builds a value (two threads
# can both miss and both build). Settings are prepared on a background thread while the
# worker may be phonemizing, so every espeak create and use goes through this lock.
_espeak_lock = threading.Lock()
_model_lock  = threading.Lock()  # same for the 1.3 GB model: load it once, not once per thread

@lru_cache(maxsize=None)
def _backend(lng_short: str) -> EspeakBackend:
    # Starting espeak is slow, so keep one backend per language. Call with _espeak_lock held.
    # No stress marks: phoneme recognition models (wav2vec2 espeak) don't output them,
    # and they'd show up as mismatches when comparing.
    return EspeakBackend(lng_short, preserve_punctuation=False, with_stress=False)

def download_model():
    """Fetch the model into MODEL_DIR if it isn't there yet (~1.3 GB, first run only)."""
    if (MODEL_DIR / MODEL_FILE).exists() and (MODEL_DIR / VOCAB_FILE).exists():
        return
    from huggingface_hub import hf_hub_download  # only needed for the one-off download
    for name in (MODEL_FILE, VOCAB_FILE):
        hf_hub_download(MODEL_REPO, name, local_dir=MODEL_DIR)

def _model() -> tuple[ort.InferenceSession, dict[int, str]]:
    with _model_lock:
        return _load_model()

@lru_cache(maxsize=1)
def _load_model() -> tuple[ort.InferenceSession, dict[int, str]]:
    # Slow to load, so do it once. Call through _model(), which holds the lock.
    download_model()
    session = ort.InferenceSession(str(MODEL_DIR / MODEL_FILE), providers=["CPUExecutionProvider"])
    vocab = json.loads((MODEL_DIR / VOCAB_FILE).read_text(encoding="utf-8"))
    return session, {i: token for token, i in vocab.items()}

RECORD_PADDING = 1.5        # reaction time before speaking + trailing silence

def init_lang(lang: str):
    with _espeak_lock:
        _backend(LANGUAGE_SHORT_FORM[lang])

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

    with _espeak_lock:
        phonemized = _backend(lng_short).phonemize([sentence], separator=_SEPARATOR, strip=True)[0]

    res = [word.split() for word in phonemized.split(_WORD_SEP) if word.strip()]
    return _flatten(res)

def _generate_from_audio(audio: np.ndarray) -> list[str]:
    """16 kHz mono float32 audio -> phonemes heard, e.g. ['h', 'ə', 'l', 'oʊ', 'w', 'ɜː', 'l', 'd']"""
    if len(audio) < SAMPLE_RATE // 10:  # under 0.1 s: too short for the model to run on
        return []
    session, id_to_token = _model()

    # Same preprocessing as the model's feature extractor: zero mean, unit variance
    audio = audio.astype(np.float32)
    x = (audio - audio.mean()) / np.sqrt(audio.var() + 1e-7)
    logits = session.run(None, {session.get_inputs()[0].name: x[None, :]})[0][0]  # (frames, vocab)

    # CTC greedy decoding: best token per frame, merge repeats, drop padding/special tokens
    phonemes, prev = [], None
    for i in logits.argmax(axis=-1):
        token = id_to_token[int(i)]
        if i != prev and token not in _SPECIAL_TOKENS:
            phonemes.append(token)
        prev = i
    return phonemes
