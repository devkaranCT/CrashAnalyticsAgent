"""
Enable and inspect the Crashlytics → BigQuery streaming export.

Firebase exposes BigQuery export through the `bigqueryLinks` resource in the
Firebase Management REST API (v1beta1).  Creating a link activates the
streaming export for ALL Firebase services (including Crashlytics) into the
`firebase_crashlytics` dataset in the linked GCP project.

Reference:
  https://firebase.google.com/docs/crashlytics/bigquery-export
  https://firebase.google.com/docs/projects/api/reference/rest/v1beta1
"""

import logging
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account as sa_module

from src.config import Settings

logger = logging.getLogger(__name__)

_FIREBASE_API = "https://firebase.googleapis.com/v1beta1"


def _bearer_token(credentials) -> str:
    """Refresh credentials and return a current Bearer token."""
    credentials.refresh(GoogleAuthRequest())
    return credentials.token


def _headers(credentials) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_bearer_token(credentials)}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# BigQuery link status
# ---------------------------------------------------------------------------


def get_bigquery_link_status(settings: Settings, credentials) -> dict[str, Any]:
    """Return whether a BigQuery export link exists for the Firebase project.

    Returns a dict with:
      - linked (bool)
      - links (list of link resources, may be empty)
    """
    url = f"{_FIREBASE_API}/projects/{settings.firebase_project_id}/bigqueryLinks"
    response = httpx.get(url, headers=_headers(credentials), timeout=30)

    if response.status_code == 404:
        return {"linked": False, "links": []}

    response.raise_for_status()
    data = response.json()
    links = data.get("bigqueryLinks", [])
    return {"linked": bool(links), "links": links}


# ---------------------------------------------------------------------------
# Enable BigQuery export
# ---------------------------------------------------------------------------


def enable_bigquery_export(settings: Settings, credentials) -> dict[str, Any]:
    """Enable the Crashlytics → BigQuery streaming export.

    Firebase does not expose a public REST API to programmatically toggle the
    BigQuery export — it must be activated once via the Firebase Console.
    This function checks whether the export is already active (dataset exists)
    and logs step-by-step instructions when it is not.

    Returns a status dict with:
      - active (bool)   — True if the dataset already exists
      - message (str)   — human-readable status
    """
    dataset_status = verify_export_dataset(settings, credentials)

    if dataset_status["exists"]:
        logger.info(
            "BigQuery export is active — dataset '%s' exists with %d table(s): %s",
            dataset_status["dataset_id"],
            dataset_status["table_count"],
            dataset_status["tables"],
        )
        return {"active": True, "message": "BigQuery export is active.", **dataset_status}

    _log_manual_instructions(settings)
    return {
        "active": False,
        "message": (
            "BigQuery export is not yet active. "
            "Follow the manual steps above to enable it in the Firebase Console."
        ),
        **dataset_status,
    }


def _log_manual_instructions(settings: Settings) -> None:
    logger.warning(
        "\n"
        "─────────────────────────────────────────────────────────────\n"
        "MANUAL STEP REQUIRED\n"
        "The BigQuery export can be enabled in the Firebase Console:\n"
        "  1. Open https://console.firebase.google.com/project/%s\n"
        "  2. Go to Crashlytics → (click a crash issue)\n"
        "     OR Project Settings → Integrations → BigQuery → Link\n"
        "  3. Click 'Enable BigQuery export'\n"
        "─────────────────────────────────────────────────────────────",
        settings.firebase_project_id,
    )


# ---------------------------------------------------------------------------
# Verify dataset exists
# ---------------------------------------------------------------------------


def verify_export_dataset(settings: Settings, credentials) -> dict[str, Any]:
    """Check that the Crashlytics BigQuery dataset has been created.

    Firebase creates the dataset automatically after the first crash event
    is exported.  Returns its metadata when available.
    """
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound

    bq = bigquery.Client(project=settings.gcp_project_id, credentials=credentials)

    try:
        dataset = bq.get_dataset(settings.bigquery_dataset_id)
        tables = list(bq.list_tables(dataset))
        return {
            "exists": True,
            "dataset_id": dataset.dataset_id,
            "location": dataset.location,
            "table_count": len(tables),
            "tables": [t.table_id for t in tables],
        }
    except NotFound:
        return {
            "exists": False,
            "dataset_id": settings.bigquery_dataset_id,
            "message": (
                "Dataset not yet created. Firebase will create it automatically "
                "after the first crash event is exported."
            ),
        }
