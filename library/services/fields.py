"""Canonical metadata registry shared by adapters, forms and tools."""

import calendar
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    group: str
    kind: str = "text"
    multi: bool = False
    id3: str = ""
    quick: bool = False
    formats: tuple = ("mp3", "flac", "wav")


_GROUPS = {
    "Track": "TITLE SUBTITLE ARTIST TRACKNUMBER TRACKTOTAL DISCNUMBER DISCTOTAL BPM KEY ISRC",
    "Release": "ALBUM ALBUMARTIST DATE ORIGINALDATE RELEASETYPE RELEASESTATUS MEDIA LABEL CATALOGNUMBER BARCODE COPYRIGHT ENCODEDBY",
    "Credits": "COMPOSER CONDUCTOR LYRICIST",
    "Classification": "GENRE MOOD LANGUAGE SCRIPT",
    "Notes": "COMMENT LYRICS",
    "Sort names": "TITLESORT ARTISTSORT ALBUMSORT ALBUMARTISTSORT",
    "ReplayGain": "REPLAYGAIN_TRACK_GAIN REPLAYGAIN_TRACK_PEAK REPLAYGAIN_ALBUM_GAIN REPLAYGAIN_ALBUM_PEAK",
    "Identifiers": "MUSICBRAINZ_TRACKID MUSICBRAINZ_ALBUMID MUSICBRAINZ_ARTISTID MUSICBRAINZ_ALBUMARTISTID MUSICBRAINZ_RELEASEGROUPID MUSICBRAINZ_WORKID ACOUSTID_ID",
}
_MAPPINGS = dict(
    zip(
        "TITLE SUBTITLE ARTIST ALBUMARTIST ALBUM DATE ORIGINALDATE GENRE COMPOSER CONDUCTOR LYRICIST COMMENT LYRICS BPM KEY LANGUAGE MOOD ISRC LABEL MEDIA COPYRIGHT ENCODEDBY TITLESORT ARTISTSORT ALBUMSORT ALBUMARTISTSORT".split(),
        "TIT2 TIT3 TPE1 TPE2 TALB TDRC TDOR TCON TCOM TPE3 TEXT COMM USLT TBPM TKEY TLAN TMOO TSRC TPUB TMED TCOP TENC TSOT TSOP TSOA TSO2".split(),
    )
)
_MB = {
    "MUSICBRAINZ_TRACKID": "MusicBrainz Release Track Id",
    "MUSICBRAINZ_ALBUMID": "MusicBrainz Album Id",
    "MUSICBRAINZ_ARTISTID": "MusicBrainz Artist Id",
    "MUSICBRAINZ_ALBUMARTISTID": "MusicBrainz Album Artist Id",
    "MUSICBRAINZ_RELEASEGROUPID": "MusicBrainz Release Group Id",
    "MUSICBRAINZ_WORKID": "MusicBrainz Work Id",
    "ACOUSTID_ID": "Acoustid Id",
}
MULTI = set("ARTIST ALBUMARTIST GENRE COMPOSER LYRICIST".split())
QUICK = set("TITLE ARTIST ALBUM ALBUMARTIST DATE GENRE TRACKNUMBER DISCNUMBER".split())
FIELDS = {}
for group, keys in _GROUPS.items():
    for key in keys.split():
        kind = "text"
        if key in {"TRACKNUMBER", "TRACKTOTAL", "DISCNUMBER", "DISCTOTAL"}:
            kind = "integer"
        elif key in {"DATE", "ORIGINALDATE"}:
            kind = "date"
        elif key == "BPM" or key.endswith("_PEAK"):
            kind = "decimal"
        elif key.endswith("_GAIN"):
            kind = "gain"
        elif key.startswith("MUSICBRAINZ_"):
            kind = "uuid"
        elif key in {"COMMENT", "LYRICS"}:
            kind = "longtext"
        mapping = _MAPPINGS.get(key, "TXXX:" + _MB.get(key, key))
        FIELDS[key] = Field(
            key, key.replace("_", " ").title(), group, kind, key in MULTI, mapping, key in QUICK
        )


def validate_patch(patch):
    if not isinstance(patch, dict):
        raise ValueError("Fields must be an object.")
    result, warnings = {}, []
    for key, values in patch.items():
        if key not in FIELDS:
            raise ValueError(f"{key}: unsupported field.")
        field = FIELDS[key]
        if isinstance(values, str):
            values = re.split(r"[;\n]", values) if field.multi else [values]
        if values is None:
            values = []
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"{key}: expected text values.")
        values = [v.replace("\x00", "").strip() for v in values if v.replace("\x00", "").strip()]
        if not field.multi and len(values) > 1:
            raise ValueError(f"{key}: only one value is supported.")
        for value in values:
            if len(value) > (65536 if field.kind == "longtext" else 1024):
                raise ValueError(f"{key}: value is too long.")
            if field.kind == "integer" and (not re.fullmatch(r"\d{1,4}", value)):
                raise ValueError(f"{key}: use an integer from 0 to 9999.")
            if field.kind == "date":
                if not re.fullmatch(r"\d{4}(-\d{2})?(-\d{2})?", value):
                    raise ValueError(f"{key}: use YYYY, YYYY-MM or YYYY-MM-DD.")
                parts = [int(p) for p in value.split("-")]
                y, m, d = (parts + [1, 1])[:3]
                if y < 1 or not 1 <= m <= 12 or not 1 <= d <= calendar.monthrange(y, m)[1]:
                    raise ValueError(f"{key}: impossible date.")
            if field.kind in {"decimal", "gain"}:
                try:
                    pattern = r"[+-]?\d+(?:\.\d+)?(?: dB)?" if field.kind == "gain" else r"\d+(?:\.\d+)?"
                    if not re.fullmatch(pattern, value, flags=re.ASCII):
                        raise InvalidOperation
                    number = Decimal(value.removesuffix(" dB"))
                    if not number.is_finite() or (field.kind == "decimal" and number < 0):
                        raise InvalidOperation
                    if key == "BPM" and (number > 999 or number.as_tuple().exponent < -1):
                        raise InvalidOperation
                except InvalidOperation:
                    raise ValueError(f"{key}: invalid number.") from None
            if field.kind == "uuid":
                try:
                    uuid.UUID(value)
                except ValueError:
                    warnings.append(f"{key}: unusual UUID.")
            if key == "ISRC" and not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", value):
                warnings.append("ISRC: expected 12 uppercase letters/digits.")
            if key == "BARCODE" and not re.fullmatch(r"\d{8,14}", value):
                warnings.append("Barcode: expected 8–14 digits.")
        result[key] = values
    return result, warnings


def apply_operations(tags, operations):
    patch = {}
    for key, spec in operations.items():
        mode = spec.get("mode", "replace")
        values = validate_patch({key: spec.get("values", [])})[0][key]
        current = tags.get(key, [])
        if mode == "replace":
            patch[key] = values
        elif mode == "clear":
            patch[key] = []
        elif mode in {"add", "remove"} and FIELDS[key].multi:
            patch[key] = (
                list(dict.fromkeys(current + values))
                if mode == "add"
                else [v for v in current if v not in values]
            )
        else:
            raise ValueError(f"{key}: unsupported operation {mode}.")
    return validate_patch(patch)[0]
