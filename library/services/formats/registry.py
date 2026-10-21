from pathlib import Path

from .base import AudioAdapter

EXTENSIONS = {".mp3", ".flac", ".wav"}


def adapter(path):
    if Path(path).suffix.lower() not in EXTENSIONS:
        raise ValueError("Supported audio formats: MP3, FLAC, WAV.")
    return AudioAdapter(path)
