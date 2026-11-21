import config
from app_context import AppContext
import phon
import numpy as np
import sounddevice as sd
from speaker import speak
import time

SAMPLE_RATE = 16_000  # the model only understands 16 kHz mono audio

def record(seconds: float) -> np.ndarray:
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return audio[:, 0]  # (n, 1) -> (n,)

if __name__ == "__main__":
    conf = config.get_config()

    ctx = AppContext()
    ctx.start()
    ctx.join()

    config.save_config()
