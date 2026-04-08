#!/usr/bin/env python3
"""
Smoke-test script: verify that the configured service account can read from BigQuery.

Usage:
    python scripts/verify_access.py

Exits with code 0 on success, 1 on failure.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.bigquery.client import client_from_settings
from src.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    settings = get_settings()
    logger.info("Verifying BigQuery access …")
    logger.info("Project  : %s", settings.gcp_project_id)
    logger.info("Dataset  : %s", settings.bigquery_dataset_id)
    logger.info("Key file : %s", settings.google_application_credentials)

    try:
        bq = client_from_settings(settings)
        datasets = list(bq.list_datasets())
        dataset_ids = [d.dataset_id for d in datasets]
        logger.info("✓ BigQuery access confirmed.  Visible datasets: %s", dataset_ids)

        if settings.bigquery_dataset_id in dataset_ids:
            tables = list(bq.list_tables(settings.bigquery_dataset_id))
            table_ids = [t.table_id for t in tables]
            logger.info(
                "✓ Crashlytics dataset '%s' found.  Tables: %s",
                settings.bigquery_dataset_id,
                table_ids,
            )
        else:
            logger.warning(
                "⚠  Dataset '%s' not found.  It may not have been created yet "
                "(requires at least one exported crash event).",
                settings.bigquery_dataset_id,
            )
    except Exception as exc:
        logger.error("✗ BigQuery access check failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
