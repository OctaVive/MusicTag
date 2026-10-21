import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from library.services import musicbrainz
from library.services.settings_service import set_value


@pytest.mark.django_db
def test_search_and_offline():
    cache.clear()
    set_value("musicbrainz_contact", "test@example.com")
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"releases": [{"title": "Test"}]}).encode()
    with patch("urllib.request.urlopen", return_value=response) as request:
        assert musicbrainz.search("test")[0]["title"] == "Test"
        assert musicbrainz.search("test")[0]["title"] == "Test"
        assert request.call_count == 1
    with patch("urllib.request.urlopen", side_effect=OSError("offline")), patch("time.sleep"):
        with pytest.raises(ValueError, match="unavailable"):
            musicbrainz.search("offline")


def test_release_matching_number_then_duration():
    from types import SimpleNamespace

    track = SimpleNamespace(pk=1, title="Demo", duration=120, disc_no=1, track_no=2)
    data = {
        "id": "12345678-1234-1234-1234-123456789abc",
        "title": "Album",
        "date": "2020",
        "artist-credit": [{"name": "Artist"}],
        "media": [
            {
                "position": 1,
                "track-count": 2,
                "tracks": [
                    {"id": "one", "position": 1, "title": "Different", "length": 120000},
                    {"id": "two", "position": 2, "title": "Demo", "length": 121000},
                ],
            }
        ],
    }
    patch = musicbrainz.match_release([track], data)["1"]
    assert patch["TITLE"] == ["Demo"]
    assert patch["TRACKNUMBER"] == ["2"]
