from dataclasses import dataclass
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "SpEd Packet Studio"
    app_version: str = "0.0.0"
    api_version: str = "1"
    schema_version: str = "0.6.0"
    environment: str = os.getenv("PACKET_STUDIO_ENV", "development")
    api_host: str = os.getenv("PACKET_STUDIO_API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("PACKET_STUDIO_API_PORT", "8765"))
    data_dir: Path = Path(os.getenv("PACKET_STUDIO_DATA_DIR", PROJECT_ROOT / "data")).resolve()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "packet-studio.sqlite3"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path.as_posix()}"

settings = Settings()
