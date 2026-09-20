"""
src/history.py — CSV-based detection history: read, write, clear.

Zero Streamlit imports.

Known limitation
----------------
This is a **single-user local tool**.  Concurrent writes to history.csv
from multiple processes are NOT safe — there is no file locking.
Do not deploy with multiple simultaneous users without replacing this
with a proper database backend.
"""

import os
from datetime import datetime
from typing import Any

import pandas as pd

from src.config import HISTORY_COLS, HISTORY_FILE


def load_history(path: str = HISTORY_FILE) -> pd.DataFrame:
    """
    Load detection history from a CSV file.

    Returns an empty DataFrame with the correct columns if the file does
    not exist, is empty, or is unreadable.

    Parameters
    ----------
    path : str
        Path to the history CSV.  Defaults to ``config.HISTORY_FILE``.
    """
    if not os.path.exists(path):
        return pd.DataFrame(columns=HISTORY_COLS)
    try:
        df = pd.read_csv(path)

        # Back-compat: rename old 'Confidence' column
        if "Confidence" in df.columns and "Confidence (%)" not in df.columns:
            df.rename(columns={"Confidence": "Confidence (%)"}, inplace=True)

        # Back-compat: add columns introduced in later versions
        for col in HISTORY_COLS:
            if col not in df.columns:
                df[col] = pd.NA if col in ("Confidence (%)", "AI Prob") else ""

        # Ensure numeric columns are properly typed
        df["Confidence (%)"] = pd.to_numeric(df["Confidence (%)"], errors="coerce")
        df["AI Prob"] = pd.to_numeric(df["AI Prob"], errors="coerce")

        return df[HISTORY_COLS]
    except Exception:
        return pd.DataFrame(columns=HISTORY_COLS)


def save_to_history(
    filename: str,
    verdict: str,
    confidence_pct: float,
    risk_band: str,
    prob_ai: float,
    path: str = HISTORY_FILE,
) -> None:
    """
    Append a single detection result to the history CSV.

    Parameters
    ----------
    filename : str        Original uploaded file name.
    verdict : str         Verdict string (e.g. ``"AI-Generated"``).
    confidence_pct : float Confidence percentage (0–100).
    risk_band : str       Risk band label.
    prob_ai : float       Raw P(AI-generated) probability.
    path : str            Path to history CSV.  Defaults to config value.

    Raises
    ------
    OSError
        If the CSV cannot be written (propagated to caller for UI handling).
    """
    entry: dict[str, Any] = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Filename": filename,
        "Verdict": verdict,
        "Confidence (%)": round(confidence_pct, 1),
        "Risk Band": risk_band,
        "AI Prob": round(prob_ai, 4),
    }
    df = load_history(path)
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(path, index=False)


def clear_history(path: str = HISTORY_FILE) -> None:
    """
    Overwrite the history CSV with an empty frame (preserving column headers).

    Parameters
    ----------
    path : str
        Path to history CSV.  Defaults to config value.
    """
    pd.DataFrame(columns=HISTORY_COLS).to_csv(path, index=False)
