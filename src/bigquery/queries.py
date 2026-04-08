"""
Pre-built BigQuery queries over the Crashlytics export dataset.

Firebase exports crash data into tables with this naming convention:
  <dataset>.<app_package_underscored>_ANDROID   (for Android apps)
  <dataset>.<app_package_underscored>_IOS       (for iOS apps)

Each table has a DATE-partitioned layout.  The schema documented at:
  https://firebase.google.com/docs/crashlytics/bigquery-export#export_schema
"""

import logging
from datetime import date, timedelta
from typing import Any

from google.cloud import bigquery

from src.config import Settings

logger = logging.getLogger(__name__)

Platform = str  # "ANDROID" | "IOS"


def _table_ref(settings: Settings, platform: Platform) -> str:
    """Build the fully-qualified table reference for a platform."""
    safe_pkg = settings.app_package_name.replace(".", "_").replace("-", "_")
    return (
        f"`{settings.gcp_project_id}.{settings.bigquery_dataset_id}"
        f".{safe_pkg}_{platform.upper()}`"
    )


# ---------------------------------------------------------------------------
# Top issues
# ---------------------------------------------------------------------------


def top_crash_issues(
    bq: bigquery.Client,
    settings: Settings,
    platform: Platform,
    *,
    days: int = 7,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the most frequent crash issues over the last *days* days."""
    table = _table_ref(settings, platform)
    since = (date.today() - timedelta(days=days)).isoformat()

    query = f"""
        SELECT
            issue_id,
            issue_title,
            issue_subtitle,
            COUNT(*) AS event_count,
            COUNT(DISTINCT installation_uuid) AS affected_users,
            MAX(event_timestamp) AS latest_event
        FROM {table}
        WHERE DATE(event_timestamp) >= '{since}'
          AND is_fatal = TRUE
        GROUP BY 1, 2, 3
        ORDER BY event_count DESC
        LIMIT {limit}
    """

    return _run(bq, query)


# ---------------------------------------------------------------------------
# Crash trend over time
# ---------------------------------------------------------------------------


def crash_trend(
    bq: bigquery.Client,
    settings: Settings,
    platform: Platform,
    *,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Return daily crash counts and affected-user counts for the last *days* days."""
    table = _table_ref(settings, platform)
    since = (date.today() - timedelta(days=days)).isoformat()

    query = f"""
        SELECT
            DATE(event_timestamp) AS crash_date,
            COUNT(*) AS crash_count,
            COUNT(DISTINCT installation_uuid) AS affected_users
        FROM {table}
        WHERE DATE(event_timestamp) >= '{since}'
          AND is_fatal = TRUE
        GROUP BY 1
        ORDER BY 1
    """

    return _run(bq, query)


# ---------------------------------------------------------------------------
# Issue detail
# ---------------------------------------------------------------------------


def issue_detail(
    bq: bigquery.Client,
    settings: Settings,
    platform: Platform,
    issue_id: str,
    *,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Return individual crash events for a specific issue."""
    table = _table_ref(settings, platform)
    since = (date.today() - timedelta(days=days)).isoformat()

    # Parameterise the issue_id to prevent injection
    query = f"""
        SELECT
            event_timestamp,
            installation_uuid,
            device.manufacturer AS device_manufacturer,
            device.model_name AS device_model,
            application.display_version AS app_version,
            exceptions[SAFE_OFFSET(0)].type AS exception_type,
            exceptions[SAFE_OFFSET(0)].exception_message AS exception_message,
            exceptions[SAFE_OFFSET(0)].frames[SAFE_OFFSET(0)].file AS top_frame_file,
            exceptions[SAFE_OFFSET(0)].frames[SAFE_OFFSET(0)].line AS top_frame_line
        FROM {table}
        WHERE DATE(event_timestamp) >= '{since}'
          AND issue_id = @issue_id
        ORDER BY event_timestamp DESC
        LIMIT 100
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("issue_id", "STRING", issue_id)]
    )

    return _run(bq, query, job_config=job_config)


# ---------------------------------------------------------------------------
# Affected versions
# ---------------------------------------------------------------------------


def affected_app_versions(
    bq: bigquery.Client,
    settings: Settings,
    platform: Platform,
    issue_id: str,
) -> list[dict[str, Any]]:
    """Return all app versions in which a specific issue has been seen."""
    table = _table_ref(settings, platform)

    query = f"""
        SELECT
            application.display_version AS version,
            application.build_version AS build,
            COUNT(*) AS crash_count
        FROM {table}
        WHERE issue_id = @issue_id
        GROUP BY 1, 2
        ORDER BY crash_count DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("issue_id", "STRING", issue_id)]
    )

    return _run(bq, query, job_config=job_config)


# ---------------------------------------------------------------------------
# Non-fatal events
# ---------------------------------------------------------------------------


def top_non_fatal_issues(
    bq: bigquery.Client,
    settings: Settings,
    platform: Platform,
    *,
    days: int = 7,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return the most frequent non-fatal (caught exception) issues."""
    table = _table_ref(settings, platform)
    since = (date.today() - timedelta(days=days)).isoformat()

    query = f"""
        SELECT
            issue_id,
            issue_title,
            issue_subtitle,
            COUNT(*) AS event_count,
            COUNT(DISTINCT installation_uuid) AS affected_users
        FROM {table}
        WHERE DATE(event_timestamp) >= '{since}'
          AND is_fatal = FALSE
        GROUP BY 1, 2, 3
        ORDER BY event_count DESC
        LIMIT {limit}
    """

    return _run(bq, query)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run(
    bq: bigquery.Client,
    query: str,
    job_config: bigquery.QueryJobConfig | None = None,
) -> list[dict[str, Any]]:
    from google.api_core.exceptions import NotFound

    logger.debug("Running BQ query:\n%s", query)
    try:
        job = bq.query(query, job_config=job_config)
        rows = job.result()
        return [dict(row) for row in rows]
    except NotFound:
        # Table does not exist yet — Crashlytics creates it on the first exported event.
        logger.info(
            "Crashlytics export table not found. "
            "It will be created automatically after the first crash event is exported."
        )
        return []
