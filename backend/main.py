from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import api_router
from backend.config import settings
from backend.database.migrations.runner import run_migrations

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    run_migrations()
    yield

app = FastAPI(title=settings.app_name, version=settings.app_version, docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "tauri://localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)
app.include_router(api_router, prefix=f"/api/v{settings.api_version}")
