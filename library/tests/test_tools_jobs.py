import pytest
from library.models import Job, Track
from library.services import bulk
from library.services.jobs import run
from library.services.tools import numbering, parse_filename


def test_parser():
    assert parse_filename("03 - Artist - Title.mp3", "{track} - {artist} - {title}") == {
        "TRACKNUMBER": ["3"],
        "ARTIST": ["Artist"],
        "TITLE": ["Title"],
    }
    with pytest.raises(ValueError):
        parse_filename("anything.mp3", "{bogus}")


@pytest.mark.django_db
def test_preview_apply_cancel_and_partial(indexed):
    records = list(Track.objects.all())
    selection = [t.pk for t in records]
    rows, token = bulk.preview(selection, {"GENRE": {"mode": "replace", "values": ["Jazz", "Blues"]}})
    assert len(rows) == 3
    plans = bulk.decode(token)
    (indexed / records[0].path).write_bytes(b"externally modified")
    job = Job.objects.create(kind="bulk", payload={"plans": plans})
    run(job)
    job.refresh_from_db()
    assert job.done == 3
    assert job.failed == 1
    assert job.succeeded == 2
    for track in Track.objects.exclude(pk=records[0].pk):
        assert track.tags["GENRE"] == ["Jazz", "Blues"]
    cancelled = Job.objects.create(kind="bulk", cancel_requested=True, payload={"plans": plans})
    run(cancelled)
    cancelled.refresh_from_db()
    assert cancelled.status == "cancelled"
    assert cancelled.done == 0


@pytest.mark.django_db
def test_numbering(indexed):
    tracks = list(Track.objects.order_by("filename"))
    patches = numbering(tracks, start=2, scope="folder")
    assert [patches[str(t.pk)]["TRACKNUMBER"] for t in tracks] == [["2"], ["3"], ["4"]]
    assert patches[str(tracks[0].pk)]["TRACKTOTAL"] == ["4"]


@pytest.mark.django_db
def test_noop_preview_and_cancelled_scan(indexed):
    from library.services.library_index import scan

    track = Track.objects.first()
    rows, token = bulk.preview([track.pk], {"TITLE": {"values": track.tags.get("TITLE", [])}})
    assert not rows[0]["changes"]
    assert bulk.decode(token) == []
    (indexed / track.path).unlink()
    job = Job.objects.create(kind="scan", cancel_requested=True)
    assert scan(job)["cancelled"]
    assert Track.objects.filter(pk=track.pk).exists()  # Never orphan-clean an incomplete scan.
