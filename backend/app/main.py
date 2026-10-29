from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app import database
from app.routes.ask import router as ask_router
from app.routes.documents import router as documents_router
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        database.create_schema()
    except Exception as error:
        logger.critical("Database initialization failed (%s)", type(error).__name__)
        raise RuntimeError(
            "Database initialization failed. Verify PostgreSQL availability and DATABASE_URL."
        ) from None
    yield


app = FastAPI(
    title="Policy Intelligence API",
    description="Backend API for policy document intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip() for origin in settings.frontend_origin.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["DELETE", "GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(documents_router)
app.include_router(ask_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="policy-intelligence-api")
