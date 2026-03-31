from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, TestCase, override_settings


class LockAndSaveViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_save_is_blocked_when_locked(self):
        response = self.client.post("/api/save", data={"path": "song.mp3"})
        self.assertEqual(response.status_code, 403)
        bulk_response = self.client.post(
            "/api/save-bulk",
            data='{"paths": ["song.mp3"], "ALBUM": "A"}',
            content_type="application/json",
        )
        self.assertEqual(bulk_response.status_code, 403)

    @override_settings(SUPPORTED_AUDIO_EXTENSIONS=[".mp3"])
    def test_file_endpoint_rejects_unsupported_extension(self):
        with TemporaryDirectory() as tmp:
            music_root = Path(tmp)
            (music_root / "demo.txt").write_text("x", encoding="utf-8")
            with override_settings(MUSIC_ROOT=music_root):
                response = self.client.get("/api/file", {"path": "demo.txt"})
            self.assertEqual(response.status_code, 400)

    @override_settings(SUPPORTED_AUDIO_EXTENSIONS=[".mp3"])
    def test_unlock_then_save_calls_tag_writer(self):
        with TemporaryDirectory() as tmp:
            music_root = Path(tmp)
            audio_file = music_root / "song.mp3"
            audio_file.write_bytes(b"x")

            with override_settings(MUSIC_ROOT=music_root):
                self.client.post(
                    "/api/lock",
                    data='{"unlocked": true}',
                    content_type="application/json",
                )
                with patch("tagger.views.write_audio_metadata") as write_tags, patch(
                    "tagger.views.read_audio_metadata", return_value={}
                ):
                    response = self.client.post(
                        "/api/save",
                        data={
                            "path": "song.mp3",
                            "TITLE": "T",
                            "ARTIST": "A",
                            "ALBUM": "AL",
                            "ALBUMARTIST": "AA",
                            "TRACKNUMBER": "1",
                            "GENRE": "Rock",
                            "YEAR": "2020",
                            "DISCNUMBER": "1",
                        },
                    )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(write_tags.called)

    @override_settings(SUPPORTED_AUDIO_EXTENSIONS=[".mp3"])
    def test_unlock_then_bulk_save_returns_aggregated_counts(self):
        with TemporaryDirectory() as tmp:
            music_root = Path(tmp)
            (music_root / "song1.mp3").write_bytes(b"x")
            (music_root / "song2.mp3").write_bytes(b"x")
            with override_settings(MUSIC_ROOT=music_root):
                self.client.post("/api/lock", data='{"unlocked": true}', content_type="application/json")
                with patch("tagger.views.read_audio_metadata", return_value={}), patch(
                    "tagger.views.write_audio_metadata"
                ) as write_tags:
                    response = self.client.post(
                        "/api/save-bulk",
                        data='{"paths": ["song1.mp3", "song2.mp3"], "ALBUM": "Album X"}',
                        content_type="application/json",
                    )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["updated"], 2)
            self.assertEqual(body["failed_count"], 0)
            self.assertEqual(write_tags.call_count, 2)
