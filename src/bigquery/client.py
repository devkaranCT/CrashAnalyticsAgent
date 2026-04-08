"""
Authenticated BigQuery client factory.

Credentials are loaded once from the path pointed to by
GOOGLE_APPLICATION_CREDENTIALS and cached for the process lifetime.
"""

import logging
from functools import lru_cache

from google.cloud import bigquery
from google.oauth2 import service_account

from src.config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_bq_client(credential_path: str, project_id: str) -> bigquery.Client:
    creds = service_account.Credentials.from_service_account_file(
        credential_path,
        scopes=["https://www.googleapis.com/auth/bigquery"],
    )
    client = bigquery.Client(project=project_id, credentials=creds)
    logger.info("BigQuery client initialised for project %s", project_id)
    return client


def client_from_settings(settings: Settings) -> bigquery.Client:
    return get_bq_client(
        settings.google_application_credentials,
        settings.gcp_project_id,
    )
