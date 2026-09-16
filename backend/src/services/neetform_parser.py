"""The only adapter that knows NeetoForm payload shapes and field labels."""

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from src.errors import AppError
from src.models.profile import FileInput, ProfileInput

ALIASES = {
    "name": ["name", "full_name", "full name"],
    "email": ["email", "email address", "email_address"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile url", "linkedin_url"],
    "support": ["support", "I'm willing to support this cause by", "support_raw"],
    "theme": ["theme"],
    "file": ["file_upload", "file upload", "file", "resume", "profile", "attachments"],
}


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(text(v) for v in value)
    if isinstance(value, dict):
        if "first_name" in value or "last_name" in value:
            return " ".join(
                str(value.get(k, "")) for k in ("first_name", "last_name")
            ).strip()
        for key in ("value", "label", "name", "url"):
            if key in value:
                return text(value[key])
        return ", ".join(text(v) for v in value.values())
    return str(value)


def date_value(value: Any, required: bool = False) -> str:
    if not value:
        if required:
            raise AppError("Submission date is missing.")
        return ""
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        raise AppError("Invalid submission date.") from None


def files_from(value: Any) -> list[FileInput]:
    if isinstance(value, str):
        if value.startswith(("https://", "http://")):
            return [FileInput(value)]
        try:
            parsed = json.loads(value)
            return files_from(parsed) if isinstance(parsed, (dict, list)) else []
        except ValueError:
            return []
    if isinstance(value, list):
        return [file for entry in value for file in files_from(entry)]
    if isinstance(value, dict):
        url = next(
            (
                value[k]
                for k in (
                    "url",
                    "download_url",
                    "downloadUrl",
                    "file_url",
                    "signed_url",
                )
                if isinstance(value.get(k), str)
            ),
            None,
        )
        if url:
            return [
                FileInput(
                    url,
                    str(
                        value.get("name")
                        or value.get("filename")
                        or value.get("file_name")
                        or "profile.pdf"
                    ),
                    str(value.get("id") or value.get("key") or ""),
                    str(
                        value.get("updated_at")
                        or value.get("checksum")
                        or value.get("version")
                        or ""
                    ),
                )
            ]
        return [file for child in value.values() for file in files_from(child)]
    return []


class NeetoSubmissionMapper:
    def __init__(self, mapping: dict[str, str] | None = None, form_id: str = ""):
        self.mapping = mapping or {}
        self.form_id = form_id

    def parse(self, payload: dict[str, Any]) -> ProfileInput:
        if not isinstance(payload, dict):
            raise AppError("Expected a submission object.")
        body = payload
        # API response objects, v1/v2 submission envelopes, and data envelopes.
        for _ in range(4):
            nested = next(
                (
                    body[k]
                    for k in ("webhook", "submission", "data")
                    if isinstance(body.get(k), dict)
                ),
                None,
            )
            if nested is None:
                break
            body = nested
        incoming_form = body.get("form_id") or payload.get("form_id")
        if incoming_form and self.form_id and str(incoming_form) != self.form_id:
            raise AppError("Webhook belongs to a different form.")
        sid = text(body.get("submission_id") or body.get("id")).strip()
        if not sid or len(sid) > 256:
            raise AppError("Valid submission ID is required.")
        values = {normalized(str(k)): v for k, v in body.items()}
        for collection in ("responses", "field_values", "fields", "answers"):
            entries = body.get(collection, [])
            if isinstance(entries, dict):

                for code, entry in entries.items():
                    values[normalized(str(code))] = (
                        entry.get("value", entry) if isinstance(entry, dict) else entry
                    )
                    if isinstance(entry, dict) and entry.get("field"):
                        values[normalized(str(entry["field"]))] = entry.get("value")
            elif isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        value = entry.get(
                            "value",
                            entry.get(
                                "answer", entry.get("response", entry.get("data"))
                            ),
                        )
                        for key in (
                            "id",
                            "field_id",
                            "label",
                            "slug",
                            "name",
                            "field_name",
                        ):
                            if entry.get(key):
                                values[normalized(str(entry[key]))] = value

        def value(key: str) -> Any:
            for label in [self.mapping.get(key, ""), *ALIASES[key]]:
                if normalized(label) in values:
                    return values[normalized(label)]
            return ""

        attributes = {
            key: text(value(key)).strip()
            for key in ("name", "email", "linkedin", "support", "theme")
        }
        limits = {
            "name": 300,
            "email": 320,
            "linkedin": 2048,
            "support": 12000,
            "theme": 300,
        }
        if any(len(attributes[k]) > limits[k] for k in attributes):
            raise AppError("A profile field exceeds the supported length.")
        linkedin = attributes["linkedin"]
        if linkedin and urlparse(linkedin).scheme not in ("https", "http"):
            raise AppError("LinkedIn URL must use HTTPS or HTTP.")
        dates = (
            body.get("created_at")
            or body.get("submission_date")
            or body.get("submitted_at")
        )
        files = files_from(value("file"))
        if len(files) > 10 or any(
            len(f.url) > 8192 or len(f.name) > 512 for f in files
        ):
            raise AppError("Invalid document metadata.")
        return ProfileInput(
            sid,
            attributes["name"] or "Unnamed profile",
            attributes["email"],
            linkedin,
            attributes["support"],
            attributes["theme"] or "Other",
            date_value(dates, required=True),
            date_value(body.get("updated_at")),
            files,
        )
