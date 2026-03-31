from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from tagger.services.tag_service import TagPayload, read_audio_metadata, write_audio_metadata


class TagServiceTests(SimpleTestCase):
    def test_read_audio_metadata_normalizes_values(self):
        fake_easy = {
            "title": ["Song"],
            "artist": ["Artist"],
            "album": ["Album"],
            "albumartist": ["Album Artist"],
            "tracknumber": ["2"],
            "genre": ["Rock"],
            "date": ["2024"],
            "discnumber": ["1"],
        }

        class FakeDetailed:
            pass

        with patch("tagger.services.tag_service.MutagenFile", side_effect=[fake_easy, FakeDetailed()]):
            result = read_audio_metadata(Path("dummy.mp3"))
        self.assertEqual(result["TITLE"], "Song")
        self.assertEqual(result["ARTIST"], "Artist")
        self.assertEqual(result["ALBUM"], "Album")
        self.assertEqual(result["ALBUMARTIST"], "Album Artist")
        self.assertEqual(result["TRACKNUMBER"], "2")
        self.assertEqual(result["GENRE"], "Rock")
        self.assertEqual(result["YEAR"], "2024")
        self.assertEqual(result["DISCNUMBER"], "1")

    def test_write_audio_metadata_sets_standard_fields(self):
        class FakeAudio(dict):
            def save(self):
                self["saved"] = ["yes"]

        fake_audio = FakeAudio()
        with patch("tagger.services.tag_service.MutagenFile", return_value=fake_audio):
            write_audio_metadata(
                Path("dummy.mp3"),
                TagPayload(
                    title="Title",
                    artist="Artist",
                    album="Album",
                    albumartist="Album Artist",
                    tracknumber="3",
                    genre="Rock",
                    year="2022",
                    discnumber="1",
                ),
            )
        self.assertEqual(fake_audio["title"], ["Title"])
        self.assertEqual(fake_audio["artist"], ["Artist"])
        self.assertEqual(fake_audio["album"], ["Album"])
        self.assertEqual(fake_audio["albumartist"], ["Album Artist"])
        self.assertEqual(fake_audio["tracknumber"], ["3"])
        self.assertEqual(fake_audio["genre"], ["Rock"])
        self.assertEqual(fake_audio["date"], ["2022"])
        self.assertEqual(fake_audio["discnumber"], ["1"])
        self.assertEqual(fake_audio["saved"], ["yes"])
