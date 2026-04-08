#!/usr/bin/env python3
"""
One-time script: Create and configure the Crashlytics BigQuery reader service account.

What this does:
  1. Creates the service account defined by EXPORT_SERVICE_ACCOUNT_NAME in your .env.
  2. Grants it the IAM roles listed in EXPORT_IAM_ROLES.
  3. Grants it READER access on the `firebase_crashlytics` BigQuery dataset
     (if the dataset already exists).
  4. Creates a JSON key and writes it to --output-key (default: credentials/app-key.json).

Usage:
    python scripts/setup_service_account.py [--output-key PATH]

Prerequisites:
  - GOOGLE_APPLICATION_CREDENTIALS must point to a key for an admin service
    account with:
      • roles/iam.serviceAccountAdmin
      • roles/resourcemanager.projectIamAdmin
      • roles/bigquery.dataOwner
  - .env must be populated (copy from .env.example).
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import google.auth
from google.oauth2 import service_account

from src.auth.service_account import provision_service_account
from src.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-key",
        default="credentials/app-key.json",
        help="Path where the generated service account JSON key will be written.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    settings = get_settings()

    # Ensure the output directory exists
    key_dir = os.path.dirname(args.output_key)
    if key_dir:
        os.makedirs(key_dir, exist_ok=True)

    # Use the admin credentials to perform provisioning
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    logger.info("=== Service Account Provisioning ===")
    logger.info("GCP project   : %s", settings.gcp_project_id)
    logger.info("Service acct  : %s", settings.export_service_account_email)
    logger.info("IAM roles     : %s", settings.export_iam_roles)
    logger.info("Output key    : %s", args.output_key)

    key_path = provision_service_account(settings, credentials, args.output_key)

    logger.info("\n=== Provisioning complete ===")
    logger.info("Key written to: %s", key_path)
    logger.info(
        "Set GOOGLE_APPLICATION_CREDENTIALS=%s in your .env file "
        "before starting the API server.",
        key_path,
    )


if __name__ == "__main__":
    main()
