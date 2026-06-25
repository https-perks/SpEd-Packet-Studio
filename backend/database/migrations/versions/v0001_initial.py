from sqlalchemy import Connection
from backend.database.base import Base
from backend.models import domain  # noqa: F401

def upgrade(connection: Connection) -> None:
    Base.metadata.create_all(bind=connection)
