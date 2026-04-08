#!/usr/bin/env python3
"""
One-time script: Verify / enable the Crashlytics → BigQuery export.

Firebase does not expose a public REST API for toggling the BigQuery export.
This script checks whether the export dataset already exists and, if not,
prints step-by-step instructions for enabling it in the Firebase Console.

Usage:
    python scripts/setup_bigquery_export.py

Prerequisites:
  - GOOGLE_APPLICATION_CREDENTIALS must point to a service account key that
    has at least `roles/bigquery.metadataViewer` on the GCP project.
  - Copy .env.example to .env and fill in all required values.
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import google.auth
from src.config import get_settings
from src.firebase.bigquery_export import enable_bigquery_export, verify_export_dataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    settings = get_settings()

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    logger.info("=== Crashlytics → BigQuery Export Setup ===")
    logger.info("Firebase project : %s", settings.firebase_project_id)
    logger.info("GCP project      : %s", settings.gcp_project_id)
    logger.info("BigQuery dataset : %s", settings.bigquery_dataset_id)
    logger.info("App package      : %s", settings.app_package_name)

    logger.info("\n[1/1] Checking BigQuery export status …")
    status = enable_bigquery_export(settings, credentials)

    if status["active"]:
        logger.info("\n✓ BigQuery export is active and ready.")
        logger.info(
            "  Dataset : %s  |  Tables : %s",
            status.get("dataset_id"),
            status.get("tables"),
        )
        logger.info(
            "\nNext step: run `python scripts/setup_service_account.py` to "
            "provision the read-only service account."
        )
    else:
        logger.warning(
            "\n⚠  BigQuery export not yet active.\n"
            "   Complete the manual step above, then re-run this script\n"
            "   to confirm the dataset has been created."
        )
        logger.info(
            "\nAlternatively, you can skip ahead and run:\n"
            "   python scripts/setup_service_account.py\n"
            "The service account will be provisioned now; dataset access\n"
            "will be granted automatically the next time this script succeeds."
        )


if __name__ == "__main__":
    main()
