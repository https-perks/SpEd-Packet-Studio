from typing import Literal
from pydantic import BaseModel, ConfigDict
class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
class DatabaseStatus(ApiSchema):
    status: Literal["ready"]
    dialect: Literal["sqlite"]
    schema_version: str
class HealthResponse(ApiSchema):
    status: Literal["ok"]
    service: str
    app_version: str
    api_version: str
    database: DatabaseStatus
    pdf_engine: Literal["weasyprint"]
