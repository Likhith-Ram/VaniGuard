"""
src/pipeline.py — Public façade re-exporting all pipeline symbols.

Import from here for a stable API surface:

    from src.pipeline import (
        _decode_audio_bytes,
        preprocess_audio,
        load_model,
        run_inference,
        classify,
        load_history,
        save_to_history,
        clear_history,
    )

The internal split (audio_io / features / model / classify / history) is an
implementation detail — consumers only need to know this module.
"""

from src.audio_io import _decode_audio_bytes  # noqa: F401
from src.classify import classify              # noqa: F401
from src.config import (                      # noqa: F401
    DURATION,
    HOP_LENGTH,
    HISTORY_COLS,
    HISTORY_FILE,
    MIN_DURATION,
    MODEL_PATH,
    N_FFT,
    N_MELS,
    SAMPLE_RATE,
    THRESH_HIGH,
    THRESH_SUS,
    THRESH_UNCERTAIN,
)
from src.features import preprocess_audio      # noqa: F401
from src.history import (                      # noqa: F401
    clear_history,
    load_history,
    save_to_history,
)
from src.model import load_model, run_inference  # noqa: F401
