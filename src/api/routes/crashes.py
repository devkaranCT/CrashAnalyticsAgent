"""
Crash data endpoints — reads from the Crashlytics BigQuery export.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.bigquery import client as bq_client_module
from src.bigquery import queries
from src.config import Settings, get_settings

router = APIRouter(prefix="/crashes", tags=["crashes"])

Platform = Literal["ANDROID", "IOS"]


def _bq(settings: Settings = Depends(get_settings)):
    return bq_client_module.client_from_settings(settings)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TopIssue(BaseModel):
    issue_id: str
    issue_title: str | None
    issue_subtitle: str | None
    event_count: int
    affected_users: int
    latest_event: Any


class TrendPoint(BaseModel):
    crash_date: Any
    crash_count: int
    affected_users: int


class CrashEvent(BaseModel):
    event_timestamp: Any
    installation_uuid: str | None
    device_manufacturer: str | None
    device_model: str | None
    app_version: str | None
    exception_type: str | None
    exception_message: str | None
    top_frame_file: str | None
    top_frame_line: int | None


class AffectedVersion(BaseModel):
    version: str | None
    build: str | None
    crash_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/top-issues", response_model=list[TopIssue])
def get_top_issues(
    platform: Platform = Query(default="ANDROID"),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
    bq=Depends(_bq),
):
    """Return the most frequent fatal crash issues."""
    return queries.top_crash_issues(bq, settings, platform, days=days, limit=limit)


@router.get("/trend", response_model=list[TrendPoint])
def get_crash_trend(
    platform: Platform = Query(default="ANDROID"),
    days: int = Query(default=30, ge=1, le=180),
    settings: Settings = Depends(get_settings),
    bq=Depends(_bq),
):
    """Return daily crash counts over the specified window."""
    return queries.crash_trend(bq, settings, platform, days=days)


@router.get("/issues/{issue_id}", response_model=list[CrashEvent])
def get_issue_events(
    issue_id: str,
    platform: Platform = Query(default="ANDROID"),
    days: int = Query(default=7, ge=1, le=90),
    settings: Settings = Depends(get_settings),
    bq=Depends(_bq),
):
    """Return individual crash events for a specific issue ID."""
    return queries.issue_detail(bq, settings, platform, issue_id, days=days)


@router.get("/issues/{issue_id}/versions", response_model=list[AffectedVersion])
def get_affected_versions(
    issue_id: str,
    platform: Platform = Query(default="ANDROID"),
    settings: Settings = Depends(get_settings),
    bq=Depends(_bq),
):
    """Return all app versions in which a specific issue has been recorded."""
    return queries.affected_app_versions(bq, settings, platform, issue_id)


@router.get("/non-fatal", response_model=list[TopIssue])
def get_non_fatal_issues(
    platform: Platform = Query(default="ANDROID"),
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(get_settings),
    bq=Depends(_bq),
):
    """Return the most frequent non-fatal (caught exception) issues."""
    return queries.top_non_fatal_issues(bq, settings, platform, days=days, limit=limit)
