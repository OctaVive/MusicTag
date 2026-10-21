import pytest

from library.models import Operation, OperationEntry, Track
from library.services import covers
from library.services.formats.registry import adapter
from library.services.writer import fingerprint, undo, write
from .test_formats import cover_bytes


@pytest.mark.django_db
def test_write_undo_redo(indexed):
    track = Track.objects.get(format="wav")
    original = (indexed / track.path).read_bytes()
    cover_hash = covers.cache(cover_bytes())
    entry, _ = write(track, {"TITLE": ["Changed"], "ARTIST": ["One", "Two"]}, cover_hash=cover_hash)
    changed = (indexed / track.path).read_bytes()
    assert entry.status == "success"
    track.refresh_from_db()
    assert track.title == "Changed"
    assert track.cover_hash == cover_hash
    restored = undo(entry.operation_id)
    assert restored.status == "success"
    assert (indexed / track.path).read_bytes() == original
    redo = undo(restored.pk)
    assert redo.status == "success"
    assert (indexed / track.path).read_bytes() == changed


@pytest.mark.django_db
def test_failed_verification_restores_exact_bytes(indexed, monkeypatch):
    from library.services.formats.base import AudioAdapter

    track = Track.objects.get(format="wav")
    path = indexed / track.path
    original = path.read_bytes()
    real_write = AudioAdapter.write

    def bad_write(self, patch, *args, **kwargs):
        real_write(self, {"TITLE": ["Wrong"]}, *args, **kwargs)

    monkeypatch.setattr(AudioAdapter, "write", bad_write)
    with pytest.raises(ValueError, match="Verification failed"):
        write(track, {"TITLE": ["Expected"]})
    assert path.read_bytes() == original
    assert OperationEntry.objects.get().status == "failed"


@pytest.mark.django_db
def test_drift_undo_guard_and_validation(indexed):
    track = Track.objects.get(format="mp3")
    path = indexed / track.path
    expected = fingerprint(path)
    entry, _ = write(track, {"TITLE": ["Changed"]})
    with pytest.raises(ValueError, match="changed since preview"):
        write(track, {"TITLE": ["Stale"]}, expected=expected)
    adapter(path).write({"TITLE": ["External"]})
    result = undo(entry.operation_id)
    assert result.status == "partial"
    assert adapter(path).read().tags["TITLE"] == ["External"]
    count = Operation.objects.count()
    with pytest.raises(ValueError):
        write(track, {"DATE": ["not a date"]})
    assert Operation.objects.count() == count


@pytest.mark.django_db
def test_corrupt_backup_never_restored(indexed, settings):
    track = Track.objects.get(format="wav")
    entry, _ = write(track, {"TITLE": ["Changed"]})
    (settings.STATE_DIR / entry.backup).write_bytes(b"corrupt backup")
    result = undo(entry.operation_id)
    assert result.status == "partial"
    assert "integrity" in result.entries.get().error
    assert adapter(indexed / track.path).read().tags["TITLE"] == ["Changed"]
