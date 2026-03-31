from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from tagger.services.file_scanner import ScanConfig, build_tree, is_safe_relative_path


class FileScannerTests(SimpleTestCase):
    def test_build_tree_keeps_supported_extensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Album").mkdir()
            (root / "Album" / "song1.mp3").write_bytes(b"")
            (root / "Album" / "song2.flac").write_bytes(b"")
            (root / "Album" / "notes.txt").write_text("ignore", encoding="utf-8")

            tree = build_tree(ScanConfig(root=root, allowed_extensions={".mp3", ".flac", ".wav"}))
            album_node = tree["children"][0]
            file_names = [child["name"] for child in album_node["children"]]
            self.assertEqual(sorted(file_names), ["song1.mp3", "song2.flac"])

    def test_is_safe_relative_path_blocks_escape(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertRaises(ValueError, is_safe_relative_path, root, "../etc/passwd")
