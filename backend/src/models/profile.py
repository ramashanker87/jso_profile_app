from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid5

NAMESPACE = UUID("a046c680-dcb3-4ec9-b914-5434c96c7f2a")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def profile_id(form_id: str, submission_id: str) -> str:
    # Stable internal UUID prevents duplicate identities without a second index or race.
    return str(uuid5(NAMESPACE, form_id + ":" + submission_id))


@dataclass(frozen=True)
class FileInput:
    url: str
    name: str = "profile.pdf"
    identity: str = ""
    version: str = ""


@dataclass(frozen=True)
class ProfileInput:
    submission_id: str
    name: str
    email: str
    linkedin_url: str
    support_raw: str
    theme: str
    submission_date: str
    source_updated_at: str
    files: list[FileInput] = field(default_factory=list)
    source: str = "neetoform"
    member: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileInput":
        return cls(
            **{**data, "files": [FileInput(**item) for item in data.get("files", [])]}
        )


def public_profile(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "member",
        "profileId",
        "submissionId",
        "name",
        "email",
        "linkedinUrl",
        "support",
        "supportRaw",
        "theme",
        "submissionDate",
        "lastSyncedAt",
        "source",
        "createdAt",
        "updatedAt",
        "syncStatus",
        "syncError",
    )
    result = {k: item.get(k) for k in keys}
    document = item.get("pdf")
    result["pdf"] = (
        {k: document[k] for k in ("fileName", "contentType", "size") if k in document}
        if document
        else None
    )
    return result
