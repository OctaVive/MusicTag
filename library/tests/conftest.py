import shutil
from pathlib import Path

import pytest

from library.services.settings_service import configure_root


@pytest.fixture(autouse=True)
def isolated_state(settings, tmp_path):
    settings.STATE_DIR = tmp_path / "state"
    settings.STATE_DIR.mkdir()
    settings.MUSICTAG_WORKER = False


@pytest.fixture
def music(tmp_path, db):
    folder = tmp_path / "music"
    folder.mkdir()
    for fixture in (Path(__file__).parent / "fixtures").glob("silence.*"):
        shutil.copy2(fixture, folder / fixture.name)
    configure_root(str(folder))
    return folder


@pytest.fixture
def indexed(music):
    from library.services.library_index import scan

    scan()
    return music


@pytest.fixture
def unlocked(client):
    session = client.session
    session["unlocked"] = True
    session.save()
    return client
