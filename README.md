# Crash Analytics Agent API

A Python/FastAPI service that:

1. **Enables** the Firebase Crashlytics → BigQuery streaming export programmatically.
2. **Provisions** a least-privilege service account with the IAM roles required to read the exported crash data.
3. **Exposes** a structured REST API over the crash data for downstream agents and dashboards.

---

## Architecture

```
Firebase Crashlytics
        │  (streaming export)
        ▼
BigQuery: firebase_crashlytics dataset
        │  (read via service account)
        ▼
Crash Analytics Agent API  (FastAPI)
        │
        ▼
  Your agent / dashboard
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.11 | Uses `X \| Y` union syntax |
| A GCP / Firebase project | With Crashlytics already enabled in the Firebase Console |
| An **admin** service account key | Used only for the one-time setup scripts (needs `roles/firebase.admin`, `roles/iam.serviceAccountAdmin`, `roles/resourcemanager.projectIamAdmin`, `roles/bigquery.admin`) |

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in GCP_PROJECT_ID, FIREBASE_PROJECT_ID, APP_PACKAGE_NAME at minimum
```

### 3. Point at your admin key

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/admin-key.json
```

### 4. Enable the Crashlytics → BigQuery export

```bash
python scripts/setup_bigquery_export.py
```

This calls the Firebase Management API to link BigQuery to your Firebase project
and enable the Crashlytics streaming export flag.

> **Note:** Firebase will create the `firebase_crashlytics` dataset automatically
> on the first crash event it exports.  The script reports if the dataset does
> not yet exist — this is normal for brand-new setups.

### 5. Provision the read-only service account

```bash
python scripts/setup_service_account.py --output-key credentials/app-key.json
```

What this does:
- Creates the `crashlytics-bq-reader` service account (or skips if it exists).
- Grants `roles/bigquery.dataViewer`, `roles/bigquery.jobUser`, and
  `roles/bigquery.metadataViewer` on the GCP project.
- Grants `READER` access on the `firebase_crashlytics` BigQuery dataset.
- Writes a JSON key to `credentials/app-key.json`.

Update `.env`:

```
GOOGLE_APPLICATION_CREDENTIALS=credentials/app-key.json
```

### 6. Verify access

```bash
python scripts/verify_access.py
```

### 7. Start the API server

```bash
uvicorn src.main:app --reload
```

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Reference

All routes are prefixed with `/api/v1`.

### Crash Data

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/crashes/top-issues` | Most frequent fatal crash issues (`?platform=ANDROID&days=7&limit=20`) |
| `GET` | `/crashes/trend` | Daily crash counts over a rolling window (`?platform=ANDROID&days=30`) |
| `GET` | `/crashes/issues/{issue_id}` | Individual crash events for one issue |
| `GET` | `/crashes/issues/{issue_id}/versions` | App versions affected by an issue |
| `GET` | `/crashes/non-fatal` | Most frequent non-fatal (caught exception) issues |

### Export Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/export/status` | Whether BigQuery export is currently linked |
| `POST` | `/export/enable` | Enable the export (idempotent) |
| `GET` | `/export/dataset` | Whether the Crashlytics dataset exists and its tables |

---

## Project Structure

```
src/
  config.py                  # Pydantic-settings configuration
  main.py                    # FastAPI app factory
  auth/
    service_account.py       # Create SA, grant IAM roles, issue key
  firebase/
    crashlytics.py           # Firebase Admin SDK initialisation
    bigquery_export.py       # Enable and inspect the BQ export
  bigquery/
    client.py                # Authenticated BigQuery client
    queries.py               # Pre-built crash data queries
  api/routes/
    crashes.py               # Crash data endpoints
    export.py                # Export management endpoints
scripts/
  setup_bigquery_export.py   # One-time: enable BQ export
  setup_service_account.py   # One-time: provision service account + key
  verify_access.py           # Smoke-test BigQuery access
```

---

## IAM Roles Reference

### Admin account (setup scripts only)

| Role | Why |
|---|---|
| `roles/firebase.admin` | Call the Firebase Management API |
| `roles/iam.serviceAccountAdmin` | Create service accounts and keys |
| `roles/resourcemanager.projectIamAdmin` | Grant project-level IAM roles |
| `roles/bigquery.admin` | Read/update dataset ACLs |

### App service account (runtime)

| Role | Why |
|---|---|
| `roles/bigquery.dataViewer` | Read table data |
| `roles/bigquery.jobUser` | Run query jobs |
| `roles/bigquery.metadataViewer` | List datasets and tables |

---

## Security Notes

- **Never commit** `credentials/` or any `.json` key files to version control.
  A `.gitignore` entry is strongly recommended:
  ```
  credentials/
  *.json
  .env
  ```
- The app service account is granted read-only BigQuery roles only; it cannot
  modify, delete, or export data outside of running SQL queries.
- All external inputs (query parameters, path parameters) are validated by
  FastAPI/Pydantic before reaching business logic.
