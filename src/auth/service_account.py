"""
Provision and configure the Crashlytics BigQuery reader service account.

Responsibilities:
  1. Create the service account in IAM if it does not already exist.
  2. Grant the required project-level IAM roles.
  3. Grant dataset-level BigQuery access.
  4. Create and return a JSON key for the service account.

All operations are idempotent: running this module multiple times against
an already-provisioned project is safe.
"""

import json
import logging

from googleapiclient import discovery
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from google.cloud import bigquery
from google.cloud import resourcemanager_v3
from google.iam.v1 import iam_policy_pb2, policy_pb2

from src.config import Settings

logger = logging.getLogger(__name__)

# Scopes required for the IAM and Service Account APIs
_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _iam_service(credentials):
    return discovery.build("iam", "v1", credentials=credentials, cache_discovery=False)


def _crm_service(credentials):
    return discovery.build("cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False)


# ---------------------------------------------------------------------------
# Service account creation
# ---------------------------------------------------------------------------


def ensure_service_account(settings: Settings, credentials) -> dict:
    """Create the export service account if it does not already exist.

    Returns the service account resource dict.
    """
    iam = _iam_service(credentials)
    resource_name = (
        f"projects/{settings.gcp_project_id}/serviceAccounts/"
        f"{settings.export_service_account_email}"
    )

    try:
        account = iam.projects().serviceAccounts().get(name=resource_name).execute()
        logger.info("Service account already exists: %s", settings.export_service_account_email)
        return account
    except HttpError as exc:
        if exc.resp.status != 404:
            raise

    logger.info("Creating service account: %s", settings.export_service_account_email)
    body = {
        "accountId": settings.export_service_account_name,
        "serviceAccount": {
            "displayName": settings.export_service_account_display_name,
            "description": "Reads Crashlytics crash data exported to BigQuery.",
        },
    }
    account = (
        iam.projects()
        .serviceAccounts()
        .create(name=f"projects/{settings.gcp_project_id}", body=body)
        .execute()
    )
    logger.info("Created service account: %s", account["email"])
    return account


# ---------------------------------------------------------------------------
# Project-level IAM roles
# ---------------------------------------------------------------------------


def grant_project_iam_roles(settings: Settings, credentials) -> None:
    """Add the required IAM roles to the service account on the GCP project."""
    crm = _crm_service(credentials)
    project = settings.gcp_project_id
    member = f"serviceAccount:{settings.export_service_account_email}"

    policy = crm.projects().getIamPolicy(resource=project, body={}).execute()
    bindings: list[dict] = policy.setdefault("bindings", [])

    roles_to_add = set(settings.export_iam_roles)
    existing_roles = {b["role"] for b in bindings if member in b.get("members", [])}
    roles_needed = roles_to_add - existing_roles

    if not roles_needed:
        logger.info("All required IAM roles already granted to %s", member)
        return

    for role in roles_needed:
        logger.info("Granting %s to %s", role, member)
        binding = next((b for b in bindings if b["role"] == role), None)
        if binding:
            binding["members"].append(member)
        else:
            bindings.append({"role": role, "members": [member]})

    crm.projects().setIamPolicy(resource=project, body={"policy": policy}).execute()
    logger.info("Project IAM policy updated.")


# ---------------------------------------------------------------------------
# Dataset-level BigQuery access
# ---------------------------------------------------------------------------


def grant_dataset_access(settings: Settings, credentials) -> None:
    """Grant the service account read access to the Crashlytics BigQuery dataset."""
    bq_client = bigquery.Client(project=settings.gcp_project_id, credentials=credentials)
    dataset_ref = bq_client.dataset(settings.bigquery_dataset_id)

    try:
        dataset = bq_client.get_dataset(dataset_ref)
    except Exception:
        logger.warning(
            "Dataset %s not found — it will be created automatically when the "
            "Crashlytics export runs for the first time. "
            "Dataset-level ACL will need to be applied after the dataset exists.",
            settings.bigquery_dataset_id,
        )
        return

    member_entry = bigquery.AccessEntry(
        role="READER",
        entity_type="userByEmail",
        entity_id=settings.export_service_account_email,
    )

    current_access = list(dataset.access_entries)
    already_granted = any(
        e.entity_id == settings.export_service_account_email for e in current_access
    )

    if already_granted:
        logger.info(
            "Dataset access already granted to %s", settings.export_service_account_email
        )
        return

    dataset.access_entries = current_access + [member_entry]
    bq_client.update_dataset(dataset, ["access_entries"])
    logger.info(
        "Granted READER access on dataset %s to %s",
        settings.bigquery_dataset_id,
        settings.export_service_account_email,
    )


# ---------------------------------------------------------------------------
# Key creation
# ---------------------------------------------------------------------------


def create_service_account_key(settings: Settings, credentials) -> dict:
    """Create and return a new JSON key for the export service account.

    The returned dict is the raw service account key JSON that should be
    written to a secure location and referenced via GOOGLE_APPLICATION_CREDENTIALS.
    """
    iam = _iam_service(credentials)
    resource_name = (
        f"projects/{settings.gcp_project_id}/serviceAccounts/"
        f"{settings.export_service_account_email}"
    )

    response = (
        iam.projects()
        .serviceAccounts()
        .keys()
        .create(name=resource_name, body={"privateKeyType": "TYPE_GOOGLE_CREDENTIALS_FILE"})
        .execute()
    )

    import base64

    key_json = base64.b64decode(response["privateKeyData"]).decode("utf-8")
    logger.info(
        "Created key %s for service account %s",
        response["name"],
        settings.export_service_account_email,
    )
    return json.loads(key_json)


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------


def provision_service_account(settings: Settings, credentials, output_key_path: str) -> str:
    """Run the full provisioning flow and write the key to *output_key_path*.

    Returns the path to the written key file.
    """
    ensure_service_account(settings, credentials)
    grant_project_iam_roles(settings, credentials)
    grant_dataset_access(settings, credentials)

    key_data = create_service_account_key(settings, credentials)
    with open(output_key_path, "w") as fh:
        json.dump(key_data, fh, indent=2)

    logger.info("Service account key written to %s", output_key_path)
    return output_key_path
