from dataclasses import dataclass
import os

from backend.paths import paths


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SpEd Packet Studio"
    app_version: str = "1.0.1"
    api_version: str = "1"
    schema_version: str = "0.6.0"
    environment: str = os.getenv("PACKET_STUDIO_ENV", "development")
    api_host: str = os.getenv("PACKET_STUDIO_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("PACKET_STUDIO_API_PORT", "8765"))
    paths = paths

    @property
    def app_data_dir(self): return self.paths.app_data_dir
    @property
    def resource_dir(self): return self.paths.resource_dir
    @property
    def data_dir(self): return self.paths.data_dir
    @property
    def settings_dir(self): return self.paths.settings_dir
    @property
    def templates_dir(self): return self.paths.templates_dir
    @property
    def brand_kits_dir(self): return self.paths.brand_kits_dir
    @property
    def backups_dir(self): return self.paths.backups_dir
    @property
    def cache_dir(self): return self.paths.cache_dir
    @property
    def database_path(self): return self.paths.database_path
    @property
    def database_url(self) -> str: return f"sqlite:///{self.database_path.as_posix()}"


settings = Settings()
