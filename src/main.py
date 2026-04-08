"""
Crash Analytics Agent API

Entry point for the FastAPI application.  Start with:

    uvicorn src.main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import crashes, export
from src.config import get_settings
from src.firebase.crashlytics import initialise as init_firebase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Crash Analytics Agent API",
        description=(
            "Reads Firebase Crashlytics crash data exported to BigQuery "
            "and surfaces it through a structured REST API."
        ),
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(crashes.router, prefix="/api/v1")
    app.include_router(export.router, prefix="/api/v1")

    @app.on_event("startup")
    async def _startup():
        init_firebase(settings)
        logger.info(
            "Application started — project=%s dataset=%s",
            settings.firebase_project_id,
            settings.bigquery_dataset_id,
        )

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
