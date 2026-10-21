import io

import pytest
from mutagen import id3
from PIL import Image

from library.services.fields import FIELDS
from library.services.formats.registry import adapter


def cover_bytes(color="red"):
    stream = io.BytesIO()
    Image.new("RGB", (12, 12), color).save(stream, "JPEG")
    return stream.getvalue()


def field_value(field):
    if field.kind == "integer":
        return ["3"]
    if field.kind == "date":
        return ["2024-02-29"]
    if field.kind == "decimal":
        return ["1.5"]
    if field.kind == "gain":
        return ["-3.5 dB"]
    if field.kind == "uuid":
        return ["12345678-1234-1234-1234-123456789abc"]
    return ["Alpha", "Beta"] if field.multi else ["A test value"]


@pytest.mark.parametrize("extension", ["mp3", "flac", "wav"])
def test_every_field_roundtrips(music, extension):
    path = music / ("silence." + extension)
    patch = {key: field_value(field) for key, field in FIELDS.items()}
    adapter(path).write(patch)
    actual = adapter(path).read().tags
    assert all(actual.get(k) == v for k, v in patch.items()), {
        k: (v, actual.get(k)) for k, v in patch.items() if actual.get(k) != v
    }
    adapter(path).write({key: [] for key in patch})
    assert not any(adapter(path).read().tags.get(key) for key in patch)


@pytest.mark.parametrize("extension", ["mp3", "flac", "wav"])
def test_covers_unknown_tags_and_other_roles(music, extension):
    path = music / ("silence." + extension)
    audio = adapter(path).audio
    if audio.tags is None:
        audio.add_tags()
    if extension == "flac":
        from mutagen.flac import Picture

        audio["UNRELATED"] = ["keep me"]
        picture = Picture()
        picture.type, picture.mime, picture.data = 4, "image/jpeg", cover_bytes("blue")
        audio.add_picture(picture)
    else:
        audio.tags.add(id3.TXXX(encoding=3, desc="UNRELATED", text=["keep me"]))
        audio.tags.add(id3.APIC(encoding=3, mime="image/jpeg", type=4, desc="back", data=cover_bytes("blue")))
    audio.save()
    front = cover_bytes()
    adapter(path).write({"TITLE": ["Changed"]}, front, True)
    assert adapter(path).read().cover == front
    adapter(path).write({}, cover_changed=True)
    assert adapter(path).read().cover is None
    audio = adapter(path).audio
    if extension == "flac":
        assert audio["UNRELATED"] == ["keep me"]
        assert any(p.type == 4 for p in audio.pictures)
    else:
        assert audio.tags["TXXX:UNRELATED"].text == ["keep me"]
        assert any(p.type == 4 for p in audio.tags.getall("APIC"))


@pytest.mark.parametrize("extension", ["mp3", "flac", "wav"])
def test_patch_totals_and_date_precision(music, extension):
    path = music / ("silence." + extension)
    adapter(path).write({"TRACKNUMBER": ["1"], "TRACKTOTAL": ["12"], "DATE": ["2020"]})
    adapter(path).write({"TRACKNUMBER": ["2"]})
    tags = adapter(path).read().tags
    assert tags["TRACKTOTAL"] == ["12"]
    assert tags["DATE"] == ["2020"]


@pytest.mark.parametrize("extension", ["mp3", "wav"])
def test_id3_v23_multi_and_clearing_number(music, extension):
    path = music / ("silence." + extension)
    adapter(path).write({"ARTIST": ["One", "Two"], "TRACKNUMBER": ["1"], "TRACKTOTAL": ["12"]}, version=3)
    assert adapter(path).read().tags["ARTIST"] == ["One", "Two"]
    adapter(path).write({"TRACKNUMBER": []})
    tags = adapter(path).read().tags
    assert not tags.get("TRACKNUMBER")
    assert tags["TRACKTOTAL"] == ["12"]
