from dataclasses import dataclass
import json
from typing import Any
import boto3
from botocore.config import Config
from src.config import Settings
from src.repositories.profile_repository import DynamoProfileRepository
from src.repositories.job_repository import DynamoJobRepository
from src.repositories.lock_repository import DynamoLockRepository
from src.services.profile_service import ProfileService
from src.services.secrets_service import SecretsService
from src.services.storage_service import S3StorageService, SafeDownloader
from src.services.sync_service import SyncService
from src.services.neetform_parser import NeetoSubmissionMapper
from src.services.neeto_service import HttpNeetoClient


@dataclass
class Runtime:
    settings: Settings
    profiles: Any
    jobs: Any
    storage: Any
    secrets: Any
    dispatch: Any
    locks: Any = None
    members: Any = None
    member_jobs: Any = None
    cognito: Any = None
    sambhav: Any = None
    job_openings: Any = None

    def job_opening_service(self):
        from src.errors import AppError
        from src.services.job_opening_service import JobOpeningService
        if self.job_openings is None:
            raise AppError("Jobs are not configured.", 503, "NOT_CONFIGURED")
        return JobOpeningService(self.job_openings, getattr(self.storage, "client", None),
                                 getattr(self.storage, "bucket", None))

    def sambhav_service(self):
        from src.services.sambhav_service import SambhavService
        return SambhavService(self.sambhav, self.members, self.storage.client, self.storage.bucket)

    def member_source(self):
        from src.services.member_neeto_service import MemberSource
        return MemberSource(HttpNeetoClient(
            self.settings.neeto_base_url, self.settings.member_form_id,
            self.secrets.get()["NEETO_API_KEY"], self.settings.local),
            self.settings.member_form_id, self.settings.member_status_field,
            self.settings.member_status_value)

    def member_sync_service(self):
        from src.services.member_neeto_service import MemberSyncService
        return MemberSyncService(self.members, self.storage, self.settings, self.locks)

    def member_service(self):
        from src.errors import AppError
        from src.services.member_service import MemberService
        if self.members is None:
            raise AppError("Member directory is not configured.", 503, "NOT_CONFIGURED")
        return MemberService(self.members, self.storage)

    def profile_service(self) -> ProfileService:
        return ProfileService(self.profiles, self.storage, bool(self.settings.google_sheet_id))

    def sync_service(self) -> SyncService:
        return SyncService(self.settings, self.profiles, self.storage, self.locks,
                           self.neeto if self.settings.google_sheet_id else None)

    def sync_mapper(self):
        if self.settings.google_sheet_id:
            from src.services.sheets_service import SheetMapper
            return SheetMapper()
        return self.mapper()

    def mapper(self) -> NeetoSubmissionMapper:
        return NeetoSubmissionMapper(self.settings.field_mapping, self.settings.form_id)

    def neeto(self) -> HttpNeetoClient:
        if self.settings.google_sheet_id:
            from src.services.sheets_service import GoogleSheetsClient
            return GoogleSheetsClient(self.settings, self.secrets)
        return HttpNeetoClient(
            self.settings.neeto_base_url,
            self.settings.form_id,
            self.secrets.get()["NEETO_API_KEY"],
            self.settings.local,
        )


def aws_runtime() -> Runtime:
    from src.repositories.job_opening_repository import DynamoJobOpeningRepository
    settings = Settings.from_env()
    session = boto3.Session(region_name=settings.region)
    config = Config(connect_timeout=5, read_timeout=20, retries={"max_attempts": 2})
    dynamodb = session.resource("dynamodb", config=config)
    lambda_client = session.client("lambda", config=config)

    def dispatch(event: dict[str, Any]) -> None:
        lambda_client.invoke(
            FunctionName=settings.worker_name,
            InvocationType="Event",
            Payload=json.dumps(event).encode(),
        )

    return Runtime(
        settings,
        DynamoProfileRepository(dynamodb.Table(settings.profile_table)),
        DynamoJobRepository(
            dynamodb.Table(settings.job_table),
            session.client("dynamodb", config=config),
        ),
        S3StorageService(
            session.client(
                "s3",
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=5,
                    read_timeout=20,
                    retries={"max_attempts": 2},
                ),
            ),
            settings.bucket,
            SafeDownloader(settings.attachment_hosts, settings.max_file_bytes),
            settings.signed_url_seconds,
        ),
        SecretsService(
            session.client("secretsmanager", config=config), settings.secret_arn
        ),
        dispatch,
        DynamoLockRepository(dynamodb.Table(settings.job_table)),
        dynamodb.Table(settings.member_table),
        DynamoJobRepository(dynamodb.Table(settings.job_table), session.client("dynamodb", config=config), kind="members"),
        session.client("cognito-idp", config=config),
        dynamodb.Table(settings.sambhav_table) if settings.sambhav_table else None,
        DynamoJobOpeningRepository(dynamodb.Table(settings.job_openings_table)) if settings.job_openings_table else None,
    )
