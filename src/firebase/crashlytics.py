"""
Firebase Admin SDK wrapper for Crashlytics.

The Admin SDK provides a thin interface to Crashlytics; rich analytics
are accessed via BigQuery (see bigquery/queries.py).  This module handles
SDK initialisation and any direct Crashlytics Admin calls.
"""

import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials as fb_credentials

from src.config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_firebase_app(credential_path: str, project_id: str) -> firebase_admin.App:
    """Initialise (or return the already-initialised) Firebase Admin app."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    cred = fb_credentials.Certificate(credential_path)
    app = firebase_admin.initialize_app(
        cred,
        options={"projectId": project_id},
    )
    logger.info("Firebase Admin app initialised for project %s", project_id)
    return app


def initialise(settings: Settings) -> firebase_admin.App:
    return get_firebase_app(
        settings.google_application_credentials,
        settings.firebase_project_id,
    )
