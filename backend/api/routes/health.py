from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database.session import get_session
from backend.schemas.system import DatabaseStatus, HealthResponse
router = APIRouter(tags=["system"])

@router.get("/health", response_model=HealthResponse)
def health_check(session: Session = Depends(get_session)) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(status="ok", service=settings.app_name, app_version=settings.app_version, api_version=settings.api_version, database=DatabaseStatus(status="ready", dialect="sqlite", schema_version=settings.schema_version), pdf_engine="weasyprint")
