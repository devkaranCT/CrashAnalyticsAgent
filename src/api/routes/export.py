"""
Export management endpoints — inspect and enable the Crashlytics → BigQuery export.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from google.oauth2 import service_account as sa_module

from src.config import Settings, get_settings
from src.firebase import bigquery_export

router = APIRouter(prefix="/export", tags=["export"])


def _admin_credentials(settings: Settings = Depends(get_settings)):
    """Return service-account credentials scoped for Firebase + BigQuery management."""
    return sa_module.Credentials.from_service_account_file(
        settings.google_application_credentials,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ExportStatus(BaseModel):
    linked: bool
    details: dict | None = None


class DatasetStatus(BaseModel):
    exists: bool
    dataset_id: str
    location: str | None = None
    table_count: int | None = None
    tables: list[str] | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ExportStatus)
def get_export_status(
    settings: Settings = Depends(get_settings),
    credentials=Depends(_admin_credentials),
):
    """Return whether the Crashlytics → BigQuery export is currently enabled.

    Uses dataset existence as the source of truth (the bigqueryLinks REST
    endpoint is not publicly available).
    """
    dataset = bigquery_export.verify_export_dataset(settings, credentials)
    return {"linked": dataset["exists"], "details": dataset}


@router.post("/enable", response_model=ExportStatus)
def enable_export(
    settings: Settings = Depends(get_settings),
    credentials=Depends(_admin_credentials),
):
    """Enable the Crashlytics → BigQuery streaming export."""
    return bigquery_export.enable_bigquery_export(settings, credentials)


@router.get("/dataset", response_model=DatasetStatus)
def get_dataset_status(
    settings: Settings = Depends(get_settings),
    credentials=Depends(_admin_credentials),
):
    """Check whether the Firebase-managed BigQuery dataset exists and list its tables."""
    return bigquery_export.verify_export_dataset(settings, credentials)
