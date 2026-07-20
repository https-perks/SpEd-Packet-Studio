from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import sys

APP_NAME = "SpEd Packet Studio"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGGER = logging.getLogger("sped_packet_studio.paths")


def _env_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser().resolve() if value else None


def _app_data_root() -> Path:
    if explicit := _env_path("SPED_PACKET_APP_DATA_DIR"):
        return explicit
    if legacy_data := _env_path("PACKET_STUDIO_DATA_DIR"):
        # Backward-compatible test/development override: historically this
        # variable named the complete writable root.
        return legacy_data
    if local_app_data := os.getenv("LOCALAPPDATA", "").strip():
        return (Path(local_app_data) / APP_NAME).resolve()
    return (Path.home() / ".local" / "share" / APP_NAME).resolve()


def _resource_root() -> Path:
    if explicit := _env_path("SPED_PACKET_RESOURCE_DIR"):
        return explicit
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()
    return PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class AppPaths:
    app_data_dir: Path
    resource_dir: Path
    data_dir: Path
    settings_dir: Path
    templates_dir: Path
    brand_kits_dir: Path
    imports_dir: Path
    backups_dir: Path
    logs_dir: Path
    cache_dir: Path
    temp_dir: Path

    # Short aliases keep storage call sites readable while the explicit names
    # make the public path contract unambiguous.
    @property
    def root(self) -> Path: return self.app_data_dir
    @property
    def resources(self) -> Path: return self.resource_dir
    @property
    def data(self) -> Path: return self.data_dir
    @property
    def settings(self) -> Path: return self.settings_dir
    @property
    def templates(self) -> Path: return self.templates_dir
    @property
    def brand_kits(self) -> Path: return self.brand_kits_dir
    @property
    def imports(self) -> Path: return self.imports_dir
    @property
    def backups(self) -> Path: return self.backups_dir
    @property
    def logs(self) -> Path: return self.logs_dir
    @property
    def cache(self) -> Path: return self.cache_dir
    @property
    def temp(self) -> Path: return self.temp_dir
    @property
    def database(self) -> Path: return self.database_path
    @property
    def builtin_assets(self) -> Path: return self.builtin_assets_dir

    @classmethod
    def resolve(cls) -> "AppPaths":
        root = _app_data_root()
        return cls(
            app_data_dir=root,
            resource_dir=_resource_root(),
            data_dir=_env_path("PACKET_STUDIO_DATA_DIR") or root / "data",
            settings_dir=root / "settings",
            templates_dir=root / "templates",
            brand_kits_dir=root / "brand-kits",
            imports_dir=root / "imports",
            backups_dir=root / "backups",
            logs_dir=_env_path("SPED_PACKET_LOG_DIR") or root / "logs",
            cache_dir=_env_path("SPED_PACKET_CACHE_DIR") or root / "cache",
            temp_dir=_env_path("SPED_PACKET_TEMP_DIR") or root / "temp",
        )

    @property
    def database_path(self) -> Path:
        return self.data_dir / "packet-studio.sqlite3"

    @property
    def builtin_assets_dir(self) -> Path:
        return self.resource_dir / "assets"

    @property
    def builtin_templates_dir(self) -> Path:
        return self.resource_dir / "templates"

    def directories(self) -> tuple[Path, ...]:
        return (self.app_data_dir, self.data_dir, self.settings_dir, self.templates_dir,
                self.brand_kits_dir, self.imports_dir, self.backups_dir, self.logs_dir,
                self.cache_dir, self.temp_dir)

    def initialize(self) -> None:
        try:
            for directory in self.directories():
                directory.mkdir(parents=True, exist_ok=True)
        except OSError as reason:
            raise RuntimeError(f"Cannot create application data directories under {self.app_data_dir}: {reason}") from reason
        self._migrate_legacy_data()
        self._install_seed_database()
        if not self.resource_dir.is_dir():
            raise RuntimeError(f"Packaged resource directory is missing: {self.resource_dir}")
        LOGGER.info("Application data directory: %s", self.app_data_dir)
        LOGGER.info("Packaged resource directory (read-only): %s", self.resource_dir)
        LOGGER.info("Database path: %s", self.database_path)

    def ensure(self) -> None:
        try:
            for directory in self.directories():
                directory.mkdir(parents=True, exist_ok=True)
        except OSError as reason:
            raise RuntimeError(f"Cannot create application data directories under {self.app_data_dir}: {reason}") from reason

    def migrate_legacy_data(self) -> list[str]:
        return self._migrate_legacy_data()

    def _install_seed_database(self) -> None:
        if self.database_path.exists():
            return
        candidates = (self.resource_dir / "data" / self.database_path.name,
                      self.resource_dir / "resources" / self.database_path.name)
        if seed := next((path for path in candidates if path.is_file()), None):
            shutil.copy2(seed, self.database_path)
            LOGGER.info("Installed bundled seed database")

    def _migrate_legacy_data(self) -> list[str]:
        marker = self.settings_dir / ".legacy-data-migration-v1.json"
        legacy_root = PROJECT_ROOT / "data"
        if marker.exists() or legacy_root.resolve() == self.data_dir.resolve() or not legacy_root.is_dir():
            return []
        mappings = {
            legacy_root / "packet-studio.sqlite3": self.database_path,
            legacy_root / "library" / "app-settings.json": self.settings_dir / "app-settings.json",
            legacy_root / "library" / "themes.json": self.settings_dir / "themes.json",
            legacy_root / "library" / "templates.json": self.templates_dir / "templates.json",
        }
        migrated: list[str] = []
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        legacy_db = legacy_root / "packet-studio.sqlite3"
        if legacy_db.is_file():
            shutil.copy2(legacy_db, self.backups_dir / f"legacy-database-{timestamp}.sqlite3")
        for source, destination in mappings.items():
            if source.is_file() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                migrated.append(str(source.relative_to(PROJECT_ROOT)).replace("\\", "/"))
        for name, destination in (("assets", self.brand_kits_dir), ("backups", self.backups_dir),
                                  ("exports", self.cache_dir / "generated-exports")):
            source = legacy_root / name
            if source.is_dir():
                shutil.copytree(source, destination, dirs_exist_ok=True, copy_function=_copy_without_overwrite)
                migrated.append(str(source.relative_to(PROJECT_ROOT)).replace("\\", "/"))
        marker.write_text(json.dumps({"completed_at": datetime.now(timezone.utc).isoformat(),
                                      "migrated": migrated}, indent=2), encoding="utf-8")
        if migrated:
            LOGGER.info("Migrated legacy application data: %s", ", ".join(migrated))
        return migrated


def _copy_without_overwrite(source: str, destination: str) -> str:
    if not Path(destination).exists():
        shutil.copy2(source, destination)
    return destination


paths = AppPaths.resolve()
