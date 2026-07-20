import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.paths import AppPaths


def make_paths(root: Path, resources: Path) -> AppPaths:
    return AppPaths(root, resources, root / "data", root / "settings", root / "templates",
                    root / "brand-kits", root / "imports", root / "backups", root / "logs",
                    root / "cache", root / "temp")


class AppPathsTests(unittest.TestCase):
    def test_creates_all_directories_with_spaces_and_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            resources = base / "packaged resources"
            resources.mkdir()
            paths = make_paths(base / "Ryañ" / "SpEd Packet Studio", resources)
            paths.initialize()
            for directory in paths.directories():
                self.assertTrue(directory.is_dir())

    def test_legacy_migration_copies_once_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy_root = base / "old-install"
            legacy_data = legacy_root / "data"
            legacy_data.mkdir(parents=True)
            (legacy_data / "packet-studio.sqlite3").write_bytes(b"legacy")
            resources = base / "resources"
            resources.mkdir()
            paths = make_paths(base / "local app data", resources)
            with patch("backend.paths.PROJECT_ROOT", legacy_root):
                paths.initialize()
                self.assertEqual(paths.database_path.read_bytes(), b"legacy")
                paths._migrate_legacy_data()
            marker = json.loads((paths.settings_dir / ".legacy-data-migration-v1.json").read_text(encoding="utf-8"))
            self.assertIn("data/packet-studio.sqlite3", marker["migrated"])


if __name__ == "__main__":
    unittest.main()
