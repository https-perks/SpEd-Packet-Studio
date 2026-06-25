from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar
from sqlalchemy.orm import Session
T = TypeVar("T")
@dataclass(frozen=True, slots=True)
class AutosaveResult(Generic[T]):
    value: T
    revision: str
class AutosaveService:
    """Transaction boundary for future feature autosave operations."""
    def __init__(self, session: Session) -> None: self._session = session
    def save(self, operation: Callable[[], T], revision: str) -> AutosaveResult[T]:
        try:
            value = operation(); self._session.commit(); return AutosaveResult(value=value, revision=revision)
        except Exception:
            self._session.rollback(); raise
