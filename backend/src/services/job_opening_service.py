"""Shared job links. Source websites are opened by the browser, never fetched here."""
from datetime import datetime, timezone
from hashlib import sha256
import re
from urllib.parse import urlsplit, urlunsplit

from src.errors import AppError


def normalize_url(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise AppError("Enter a job-opening link up to 4,000 characters.")
    value = value.strip()
    if re.search(r"[\s\\\x00-\x1f\x7f]", value):
        raise AppError("Enter a valid http:// or https:// job-opening link.")
    try:
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme not in ("http", "https") or not host
                or url.username is not None or url.password is not None):
            raise ValueError()
        port = url.port
        hostname = host.encode("idna").decode("ascii").lower()
        if ":" not in hostname and not re.fullmatch(r"[a-z0-9.-]+", hostname):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise AppError("Enter a valid http:// or https:// job-opening link without login credentials.") from None
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and (url.scheme, port) not in (("https", 443), ("http", 80)):
        authority += f":{port}"
    return urlunsplit((url.scheme, authority, url.path or "/", url.query, url.fragment))


class JobOpeningService:
    def __init__(self, repository):
        self.repository = repository

    def list(self):
        return {"items": sorted(self.repository.list(), key=lambda item: (item["createdAt"], item["id"]), reverse=True)}

    def create(self, body, subject):
        if not isinstance(body, dict) or set(body) - {"url", "title"}:
            raise AppError("Provide a job-opening link and optional title.")
        url = normalize_url(body.get("url"))
        title = body.get("title", "")
        if not isinstance(title, str) or len(title) > 200:
            raise AppError("Job title must be at most 200 characters.")
        item = {"id": sha256(url.encode()).hexdigest(), "url": url,
                "title": title.strip() or urlsplit(url).hostname,
                "createdAt": datetime.now(timezone.utc).isoformat(), "createdBy": subject}
        self.repository.create(item)
        return item

    def delete(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{64}", job_id):
            raise AppError("Job opening not found.", 404, "NOT_FOUND")
        self.repository.delete(job_id)
        return {"deleted": True}
