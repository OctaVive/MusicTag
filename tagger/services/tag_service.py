from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TPOS, TIT2, TPE1, TPE2, TRCK
from mutagen.mp3 import MP3
from mutagen.wave import WAVE


@dataclass(frozen=True)
class TagPayload:
    title: str
    artist: str
    album: str
    albumartist: str
    tracknumber: str
    genre: str
    year: str
    discnumber: str


def read_audio_metadata(file_path: Path) -> dict[str, Any]:
    easy = MutagenFile(str(file_path), easy=True)
    detailed = MutagenFile(str(file_path), easy=False)
    if detailed is None:
        raise ValueError("Unsupported or unreadable audio file")

    result = {
        "TITLE": _first_from_easy(easy, "title"),
        "ARTIST": _first_from_easy(easy, "artist"),
        "ALBUM": _first_from_easy(easy, "album"),
        "ALBUMARTIST": _first_from_easy(easy, "albumartist"),
        "TRACKNUMBER": _first_from_easy(easy, "tracknumber"),
        "GENRE": _first_from_easy(easy, "genre"),
        "YEAR": _first_from_easy(easy, "date"),
        "DISCNUMBER": _first_from_easy(easy, "discnumber"),
        "cover_data_url": _extract_cover_data_url(detailed),
    }
    return result


def write_audio_metadata(file_path: Path, payload: TagPayload) -> None:
    easy = MutagenFile(str(file_path), easy=True)
    if easy is None:
        raise ValueError("Unsupported audio file for tag updates")

    easy["title"] = [payload.title or ""]
    easy["artist"] = [payload.artist or ""]
    easy["album"] = [payload.album or ""]
    easy["albumartist"] = [payload.albumartist or ""]
    easy["tracknumber"] = [payload.tracknumber or ""]
    easy["genre"] = [payload.genre or ""]
    easy["date"] = [payload.year or ""]
    easy["discnumber"] = [payload.discnumber or ""]
    easy.save()


def write_cover_image(file_path: Path, filename: str, raw_bytes: bytes) -> None:
    detailed = MutagenFile(str(file_path), easy=False)
    if detailed is None:
        raise ValueError("Unsupported audio file for cover updates")

    mime_type = mimetypes.guess_type(filename)[0] or "image/jpeg"

    if isinstance(detailed, FLAC):
        detailed.clear_pictures()
        picture = Picture()
        picture.type = 3
        picture.mime = mime_type
        picture.desc = "Front cover"
        picture.data = raw_bytes
        detailed.add_picture(picture)
        detailed.save()
        return

    if isinstance(detailed, (MP3, WAVE)):
        tags = detailed.tags
        if tags is None:
            detailed.tags = ID3()
            tags = detailed.tags
        if not isinstance(tags, ID3):
            raise ValueError("Audio tags are not writable as ID3 for cover art")
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime=mime_type, type=3, desc="Front cover", data=raw_bytes))
        detailed.save()
        return

    raise ValueError("Cover updates are not implemented for this format")


def remove_cover_image(file_path: Path) -> None:
    detailed = MutagenFile(str(file_path), easy=False)
    if detailed is None:
        raise ValueError("Unsupported audio file for cover updates")
    if isinstance(detailed, FLAC):
        detailed.clear_pictures()
        detailed.save()
        return
    if isinstance(detailed, (MP3, WAVE)):
        tags = detailed.tags
        if tags is None:
            return
        if not isinstance(tags, ID3):
            raise ValueError("Audio tags are not writable as ID3 for cover art")
        tags.delall("APIC")
        detailed.save()
        return
    raise ValueError("Cover updates are not implemented for this format")


def _first_from_easy(easy_audio: Any, key: str) -> str:
    if easy_audio is None:
        return ""
    values = easy_audio.get(key, [])
    if not values:
        return ""
    return str(values[0])


def _extract_cover_data_url(audio: Any) -> str | None:
    if isinstance(audio, FLAC) and audio.pictures:
        picture = audio.pictures[0]
        encoded = base64.b64encode(picture.data).decode("ascii")
        return f"data:{picture.mime};base64,{encoded}"

    if isinstance(audio, (MP3, WAVE)) and isinstance(audio.tags, ID3):
        pictures = audio.tags.getall("APIC")
        if pictures:
            picture = pictures[0]
            encoded = base64.b64encode(picture.data).decode("ascii")
            return f"data:{picture.mime};base64,{encoded}"

    return None


def update_id3_tags_explicit(file_path: Path, payload: TagPayload) -> None:
    """
    Fallback for files where easy tags are unavailable but ID3 is valid.
    This is intentionally separate to keep normal flow simple.
    """
    audio = MutagenFile(str(file_path), easy=False)
    if not isinstance(audio, (MP3, WAVE)):
        raise ValueError("ID3 fallback is only valid for MP3/WAV files")
    tags = audio.tags
    if tags is None or not isinstance(tags, ID3):
        audio.tags = ID3()
        tags = audio.tags
    tags.delall("TIT2")
    tags.delall("TPE1")
    tags.delall("TPE2")
    tags.delall("TALB")
    tags.delall("TRCK")
    tags.delall("TCON")
    tags.delall("TDRC")
    tags.delall("TPOS")
    tags.add(TIT2(encoding=3, text=payload.title or ""))
    tags.add(TPE1(encoding=3, text=payload.artist or ""))
    tags.add(TPE2(encoding=3, text=payload.albumartist or ""))
    tags.add(TALB(encoding=3, text=payload.album or ""))
    tags.add(TRCK(encoding=3, text=payload.tracknumber or ""))
    tags.add(TCON(encoding=3, text=payload.genre or ""))
    tags.add(TDRC(encoding=3, text=payload.year or ""))
    tags.add(TPOS(encoding=3, text=payload.discnumber or ""))
    audio.save()
