from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Settings:
    sambhav_table: str = ""
    member_form_id: str = ""
    member_status_field: str = ""
    member_status_value: str = ""
    member_table: str = "jso-member-details"
    google_sheet_id: str = ""
    google_sheet_gid: str = "1259657163"
    region: str = "eu-north-1"
    profile_table: str = ""
    job_table: str = ""
    bucket: str = ""
    secret_arn: str = ""
    worker_name: str = ""
    cognito_client_id: str = ""
    cognito_pool_id: str = ""
    required_group: str = ""
    neeto_base_url: str = ""
    form_id: str = ""
    attachment_hosts: tuple[str, ...] = ()
    max_file_bytes: int = 20 * 1024 * 1024
    signed_url_seconds: int = 900
    field_mapping: dict[str, str] = field(default_factory=dict)
    local: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            sambhav_table=os.getenv("SAMBHAV_TABLE_NAME", ""),
            member_form_id=os.getenv("MEMBER_NEETO_FORM_ID", ""),
            member_status_field=os.getenv("MEMBER_NEETO_STATUS_FIELD", ""),
            member_status_value=os.getenv("MEMBER_NEETO_STATUS_VALUE", ""),
            member_table=os.getenv("MEMBER_TABLE_NAME", "jso-member-details"),
            google_sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
            google_sheet_gid=os.getenv("GOOGLE_SHEET_GID", "1259657163"),
            region=os.getenv("AWS_REGION", "eu-north-1"),
            profile_table=os.getenv("PROFILE_TABLE_NAME", ""),
            job_table=os.getenv("JOB_TABLE_NAME", ""),
            bucket=os.getenv("PROFILE_BUCKET_NAME", ""),
            secret_arn=os.getenv("NEETO_SECRET_ARN", ""),
            worker_name=os.getenv("SYNC_FUNCTION_NAME", ""),
            cognito_pool_id=os.getenv("COGNITO_USER_POOL_ID", ""),
            cognito_client_id=os.getenv("COGNITO_CLIENT_ID", ""),
            required_group=os.getenv("COGNITO_REQUIRED_GROUP", ""),
            neeto_base_url=os.getenv("NEETO_API_BASE_URL", ""),
            form_id=os.getenv("NEETO_FORM_ID", ""),
            attachment_hosts=tuple(
                h.strip().lower()
                for h in os.getenv("NEETO_ATTACHMENT_HOSTS", "").split(",")
                if h.strip()
            ),
            max_file_bytes=int(os.getenv("MAX_PROFILE_FILE_SIZE_MB", "20"))
            * 1024
            * 1024,
            signed_url_seconds=int(os.getenv("DOCUMENT_URL_EXPIRY_SECONDS", "900")),
            field_mapping={
                key: os.getenv("NEETO_FIELD_" + key.upper(), default)
                for key, default in {
                    "name": "name",
                    "email": "email",
                    "linkedin": "linkedin",
                    "support": "support",
                    "theme": "theme",
                    "file": "file_upload",
                }.items()
            },
            local=os.getenv("LOCAL_MODE") == "true",
        )
