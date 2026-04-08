from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    # GCP / Firebase project identity
    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    firebase_project_id: str = Field(..., alias="FIREBASE_PROJECT_ID")

    # Service account key file used by the application at runtime
    google_application_credentials: str = Field(..., alias="GOOGLE_APPLICATION_CREDENTIALS")

    # Service account that will be provisioned to access BigQuery exports
    export_service_account_name: str = Field(
        default="crashlytics-bq-reader",
        alias="EXPORT_SERVICE_ACCOUNT_NAME",
    )
    export_service_account_display_name: str = Field(
        default="Crashlytics BigQuery Reader",
        alias="EXPORT_SERVICE_ACCOUNT_DISPLAY_NAME",
    )

    # BigQuery dataset created by the Crashlytics export
    # Firebase creates this in the format `firebase_crashlytics`
    bigquery_dataset_id: str = Field(
        default="firebase_crashlytics",
        alias="BIGQUERY_DATASET_ID",
    )
    bigquery_location: str = Field(default="US", alias="BIGQUERY_LOCATION")

    # App bundle/package identifier used to scope Crashlytics tables
    # e.g. "com_example_myapp" (dots replaced with underscores by Firebase)
    app_package_name: str = Field(..., alias="APP_PACKAGE_NAME")

    # IAM roles granted to the export service account
    export_iam_roles: list[str] = Field(
        default=[
            "roles/bigquery.dataViewer",
            "roles/bigquery.jobUser",
            "roles/bigquery.metadataViewer",
        ],
        alias="EXPORT_IAM_ROLES",
    )

    @property
    def export_service_account_email(self) -> str:
        return f"{self.export_service_account_name}@{self.gcp_project_id}.iam.gserviceaccount.com"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
