import pytest
from library.services.fields import FIELDS, apply_operations, validate_patch


@pytest.mark.parametrize(
    "key,value",
    [
        ("TRACKNUMBER", "10000"),
        ("DISCNUMBER", "-1"),
        ("DATE", "2023-02-29"),
        ("DATE", "0000"),
        ("DATE", "2020-13"),
        ("BPM", "1000"),
        ("BPM", "1.23"),
        ("REPLAYGAIN_TRACK_PEAK", "-1"),
        ("REPLAYGAIN_ALBUM_GAIN", "NaN"),
    ],
)
def test_invalid(key, value):
    with pytest.raises(ValueError):
        validate_patch({key: [value]})


@pytest.mark.parametrize("value", ["2024", "2024-02", "2024-02-29"])
def test_dates(value):
    assert validate_patch({"DATE": [value]})[0]["DATE"] == [value]


def test_registry_and_lists():
    assert len(FIELDS) >= 44
    assert validate_patch({"ARTIST": " Alice ; Bob\nCarol "})[0] == {"ARTIST": ["Alice", "Bob", "Carol"]}
    assert validate_patch({"TITLE": " \x00Hello "})[0] == {"TITLE": ["Hello"]}
    assert validate_patch({"BARCODE": ["bad"]})[1]
    assert apply_operations({"ARTIST": ["A", "B"]}, {"ARTIST": {"mode": "add", "values": ["B", "C"]}}) == {
        "ARTIST": ["A", "B", "C"]
    }
    assert apply_operations({"ARTIST": ["A", "B"]}, {"ARTIST": {"mode": "remove", "values": ["A"]}}) == {
        "ARTIST": ["B"]
    }
    with pytest.raises(ValueError):
        validate_patch({"UNSUPPORTED": "x"})


@pytest.mark.parametrize("key,value", [("BPM", "3 dB"), ("REPLAYGAIN_TRACK_PEAK", "1e2"), ("BPM", "+10")])
def test_numeric_syntax(key, value):
    with pytest.raises(ValueError):
        validate_patch({key: [value]})
