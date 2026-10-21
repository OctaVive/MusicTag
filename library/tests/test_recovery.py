import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from library.models import Track
from library.services.writer import write


@pytest.mark.django_db
def test_pending_recovery_uses_verified_copy(indexed):
    track = Track.objects.get(format="wav")
    path = indexed / track.path
    original = path.read_bytes()
    entry, _ = write(track, {"TITLE": ["Changed"]})
    entry.status = "pending"
    entry.save()
    call_command("recover_operations", restore=True)
    assert path.read_bytes() == original
    entry.refresh_from_db()
    assert entry.status == "failed"


@pytest.mark.django_db
def test_pending_recovery_refuses_incomplete_backup(indexed, settings):
    track = Track.objects.get(format="wav")
    path = indexed / track.path
    entry, _ = write(track, {"TITLE": ["Changed"]})
    entry.status = "pending"
    entry.save()
    (settings.STATE_DIR / entry.backup).write_bytes(b"incomplete")
    current = path.read_bytes()
    with pytest.raises(CommandError):
        call_command("recover_operations", restore=True)
    assert path.read_bytes() == current
