import os

import pytest

from library.models import Album, Track
from library.services.library_index import scan
from library.services.settings_service import configure_root, contained


@pytest.mark.django_db
def test_incremental_orphans_and_errors(music):
    (music / "broken.mp3").write_bytes(b"bad")
    result = scan()
    assert result["changed"] == 4
    assert Track.objects.get(filename="broken.mp3").read_error
    assert scan()["changed"] == 0
    (music / "silence.flac").unlink()
    scan()
    assert Track.objects.count() == 3
    assert Album.objects.exists()


@pytest.mark.django_db
def test_path_containment(music, tmp_path, settings):
    outside = tmp_path / "outside.mp3"
    outside.write_bytes(b"outside")
    for value in ["../outside.mp3", str(outside), "silence.mp3/../silence.mp3"]:
        with pytest.raises(ValueError):
            contained(value)
    with pytest.raises(ValueError):
        configure_root(str(settings.STATE_DIR))
    try:
        os.symlink(outside, music / "escape.mp3")
    except OSError:
        return  # Windows often requires Developer Mode for symlinks.
    with pytest.raises(ValueError):
        contained("escape.mp3")
