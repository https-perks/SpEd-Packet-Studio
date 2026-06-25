from datetime import datetime
import uuid
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

def new_id() -> str:
    return str(uuid.uuid4())
class IdentifierMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
