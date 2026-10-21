from dataclasses import dataclass

import mutagen
from mutagen import id3
from mutagen.flac import Picture

from library.services.fields import FIELDS


@dataclass
class Snapshot:
    tags: dict
    cover: bytes | None
    mime: str
    info: dict
    raw: dict


class AudioAdapter:
    def __init__(self, path):
        self.path = path
        self.audio = mutagen.File(path, easy=False)
        if self.audio is None:
            raise ValueError("Audio file could not be recognized.")
        self.flac = path.suffix.lower() == ".flac"

    def read(self):
        tags, cover, mime = {}, None, ""
        raw = self.audio.tags or {}
        if self.flac:
            for key in FIELDS:
                values = list(raw.get(key, []))
                if key == "SUBTITLE" and not values:
                    values = list(raw.get("VERSION", []))
                if key == "ENCODEDBY" and not values:
                    values = list(raw.get("ENCODED-BY", raw.get("ENCODER", [])))
                if key in {"TRACKTOTAL", "DISCTOTAL"} and not values:
                    values = list(raw.get({"TRACKTOTAL": "TOTALTRACKS", "DISCTOTAL": "TOTALDISCS"}[key], []))
                if values:
                    tags[key] = [str(v) for v in values]
            for prefix in ["TRACK", "DISC"]:
                values = tags.get(prefix + "NUMBER", [])
                if values and "/" in values[0]:
                    number, total = values[0].split("/", 1)
                    tags[prefix + "NUMBER"] = [number] if number else []
                    tags.setdefault(prefix + "TOTAL", [total] if total else [])
            pictures = self.audio.pictures
        else:
            for key, field in FIELDS.items():
                mapping = field.id3
                if mapping.startswith("TXXX:"):
                    frame = raw.get(mapping)
                    values = list(frame.text) if frame else []
                elif mapping in {"COMM", "USLT"}:
                    frames = raw.getall(mapping) if raw else []
                    frame = next((f for f in frames if f.desc == ""), None)
                    values = ([frame.text] if mapping == "USLT" else list(frame.text)) if frame else []
                else:
                    frame = raw.get(mapping)
                    if key == "ENCODEDBY" and frame is None:
                        frame = raw.get("TSSE")
                    values = list(frame.text) if frame else []
                if values:
                    converted = [str(v) for v in values]
                    if field.multi and getattr(raw, "version", (2, 4, 0))[1] == 3:
                        converted = [part for value in converted for part in value.split("/") if part]
                    tags[key] = converted
            for prefix, frame_id in [("TRACK", "TRCK"), ("DISC", "TPOS")]:
                frame = raw.get(frame_id)
                if frame and frame.text:
                    parts = str(frame.text[0]).split("/", 1)
                    if parts[0]:
                        tags[prefix + "NUMBER"] = [parts[0]]
                    if len(parts) > 1 and parts[1]:
                        tags[prefix + "TOTAL"] = [parts[1]]
            pictures = raw.getall("APIC") if raw else []
        front = next((p for p in pictures if p.type == 3), None)
        if front:
            cover, mime = bytes(front.data), front.mime
        info = self.audio.info
        return Snapshot(
            tags,
            cover,
            mime,
            {
                key: getattr(info, source, 0) or 0
                for key, source in {
                    "duration": "length",
                    "bitrate": "bitrate",
                    "sample_rate": "sample_rate",
                    "channels": "channels",
                }.items()
            },
            {str(k): str(v)[:4096] for k, v in raw.items()},
        )

    def write(self, patch, cover=None, cover_changed=False, mime="image/jpeg", version=4):
        if self.audio.tags is None:
            self.audio.add_tags()
        raw = self.audio.tags
        current = self.read().tags
        if self.flac:
            for key, values in patch.items():
                for alias in {
                    "SUBTITLE": ["VERSION"],
                    "ENCODEDBY": ["ENCODED-BY", "ENCODER"],
                    "TRACKTOTAL": ["TOTALTRACKS"],
                    "DISCTOTAL": ["TOTALDISCS"],
                }.get(key, []):
                    if alias in raw:
                        del raw[alias]
                if values:
                    raw[key] = values
                elif key in raw:
                    del raw[key]
            if cover_changed:
                others = [p for p in self.audio.pictures if p.type != 3]
                self.audio.clear_pictures()
                for picture in others:
                    self.audio.add_picture(picture)
                if cover:
                    picture = Picture()
                    picture.type, picture.mime, picture.data = 3, mime, cover
                    from io import BytesIO
                    from PIL import Image

                    with Image.open(BytesIO(cover)) as image:
                        picture.width, picture.height = image.size
                        picture.depth = 24
                    self.audio.add_picture(picture)
            self.audio.save()
            return
        for key, values in patch.items():
            if key in {"TRACKNUMBER", "TRACKTOTAL", "DISCNUMBER", "DISCTOTAL"}:
                continue
            field = FIELDS[key]
            mapping = field.id3
            if mapping in {"COMM", "USLT"}:
                # Only canonical (empty-description) entries are replaced.
                for frame in list(raw.getall(mapping)):
                    if frame.desc == "":
                        del raw[frame.HashKey]
                if values:
                    cls = getattr(id3, mapping)
                    raw.add(
                        cls(encoding=3, lang="eng", desc="", text=values[0] if mapping == "USLT" else values)
                    )
            elif mapping.startswith("TXXX:"):
                raw.delall(mapping)
                if values:
                    raw.add(id3.TXXX(encoding=3, desc=mapping[5:], text=values))
            else:
                if key == "ENCODEDBY":
                    raw.delall("TSSE")
                raw.delall(mapping)
                if values:
                    raw.add(getattr(id3, mapping)(encoding=3, text=values))
        merged = current | patch
        for prefix, frame_id in [("TRACK", "TRCK"), ("DISC", "TPOS")]:
            if not {prefix + "NUMBER", prefix + "TOTAL"}.intersection(patch):
                continue
            number = next(iter(merged.get(prefix + "NUMBER", [])), "")
            total = next(iter(merged.get(prefix + "TOTAL", [])), "")
            raw.delall(frame_id)
            if number or total:
                raw.add(getattr(id3, frame_id)(encoding=3, text=[number + ("/" + total if total else "")]))
        if cover_changed:
            for frame in list(raw.getall("APIC")):
                if frame.type == 3:
                    del raw[frame.HashKey]
            if cover:
                description = "MusicTag front cover"
                while "APIC:" + description in raw:
                    description += " front"
                raw.add(id3.APIC(encoding=3, mime=mime, type=3, desc=description, data=cover))
        self.audio.save(v2_version=version, v23_sep="/")
