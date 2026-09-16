"""Shared job links. Source websites are opened by the browser, never fetched here."""

from copy import deepcopy
from datetime import datetime, timezone
import io
import time
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from pypdf import PdfReader
from hashlib import sha256
import re
from urllib.parse import quote, urlsplit, urlunsplit

from src.errors import AppError
from src.logging_utils import audit

MAX_SIZE = 20 * 1024 * 1024
MAX_ATTACHMENTS = 10
CATEGORIES = {"candidate-profile", "job-profile"}


def normalize_url(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise AppError("Enter a job-opening link up to 4,000 characters.")
    value = value.strip()
    if re.search(r"[\s\\\x00-\x1f\x7f]", value):
        raise AppError("Enter a valid http:// or https:// job-opening link.")
    try:
        url = urlsplit(value)
        host = url.hostname
        if (
            url.scheme not in ("http", "https")
            or not host
            or url.username is not None
            or url.password is not None
        ):
            raise ValueError()
        port = url.port
        hostname = host.encode("idna").decode("ascii").lower()
        if ":" not in hostname and not re.fullmatch(r"[a-z0-9.-]+", hostname):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise AppError(
            "Enter a valid http:// or https:// job-opening link without login credentials."
        ) from None
    authority = f"[{hostname}]" if ":" in hostname else hostname
    if port is not None and (url.scheme, port) not in (("https", 443), ("http", 80)):
        authority += f":{port}"
    return urlunsplit((url.scheme, authority, url.path or "/", url.query, url.fragment))


class JobOpeningService:
    def __init__(self, repository, s3=None, bucket=None):
        self.repository, self.s3, self.bucket = repository, s3, bucket

    @staticmethod
    def public(item):
        item = deepcopy(item)
        item.pop("version", None)
        item.setdefault("description", "")
        item.setdefault("attachments", [])
        for attachment in item["attachments"]:
            attachment.pop("s3Key", None)
        return item

    def storage_required(self):
        if self.s3 is None or not self.bucket:
            raise AppError(
                "Attachments are unavailable in the local API. Use the deployed application.",
                503,
                "NOT_CONFIGURED",
            )

    def get(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{64}", job_id):
            raise AppError("Job opening not found.", 404, "NOT_FOUND")
        item = self.repository.get(job_id)
        if not item:
            raise AppError("Job opening not found.", 404, "NOT_FOUND")
        return item

    def list(self):
        return {
            "items": [
                self.public(item)
                for item in sorted(
                    self.repository.list(),
                    key=lambda item: (item["createdAt"], item["id"]),
                    reverse=True,
                )
            ],
            "uploadsEnabled": self.s3 is not None and bool(self.bucket),
        }

    def create(self, body, subject):
        if not isinstance(body, dict) or set(body) - {"url", "title", "description"}:
            raise AppError(
                "Provide a job-opening link, optional title, and optional description."
            )
        url = normalize_url(body.get("url"))
        title = body.get("title", "")
        if not isinstance(title, str) or len(title) > 200:
            raise AppError("Job title must be at most 200 characters.")
        description = body.get("description", "")
        if not isinstance(description, str) or len(description) > 2000:
            raise AppError("Description must be at most 2,000 characters.")
        item = {
            "id": sha256(url.encode()).hexdigest(),
            "url": url,
            "title": title.strip() or urlsplit(url).hostname,
            "description": description.strip(),
            "attachments": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "createdBy": subject,
        }
        self.repository.create(item)
        return self.public(item)

    def delete(self, job_id):
        if not re.fullmatch(r"[a-f0-9]{64}", job_id):
            raise AppError("Job opening not found.", 404, "NOT_FOUND")
        item = self.repository.delete(job_id)
        if item and self.s3 is not None:
            for attachment in item.get("attachments", []):
                self.cleanup(attachment["s3Key"])
        return {"deleted": True}

    def cleanup(self, key):
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            # The listing remains deleted; do not expose filenames or signed URLs in logs.
            audit("job_attachment_cleanup_failed", status="FAILED")

    def begin_upload(self, job_id, body, subject):
        self.storage_required()
        job = self.get(job_id)
        if not isinstance(body, dict) or set(body) != {"category", "fileName", "size"}:
            raise AppError("Invalid upload request.")
        category, name, size = body["category"], body["fileName"], body["size"]
        if not isinstance(category, str) or category not in CATEGORIES:
            raise AppError("Choose candidate profile or job profile.")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 180
            or not name.lower().endswith(".pdf")
            or re.search(r"[/\\\x00-\x1f\x7f]", name)
        ):
            raise AppError("Choose a PDF file with a valid filename.")
        if type(size) is not int or not 1 <= size <= MAX_SIZE:
            raise AppError("PDFs must be no larger than 20 MB.")
        if len(job.get("attachments", [])) >= MAX_ATTACHMENTS:
            raise AppError("Each job supports up to 10 attachments.")
        upload_id = str(uuid4())
        key = f"job-openings/pending/{upload_id}.pdf"
        self.repository.create(
            {
                "id": "upload:" + upload_id,
                "jobId": job_id,
                "jobCreatedAt": job["createdAt"],
                "subject": subject,
                "category": category,
                "fileName": name,
                "size": size,
                "s3Key": key,
                "expiresAt": int(time.time()) + 3600,
            }
        )
        post = self.s3.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={
                "Content-Type": "application/pdf",
                "x-amz-server-side-encryption": "AES256",
            },
            Conditions=[
                {"Content-Type": "application/pdf"},
                {"x-amz-server-side-encryption": "AES256"},
                ["content-length-range", size, size],
            ],
            ExpiresIn=300,
        )
        return {"uploadId": upload_id, **post}

    def finish_upload(self, job_id, body, subject):
        self.storage_required()
        if (
            not isinstance(body, dict)
            or set(body) != {"uploadId"}
            or not isinstance(body["uploadId"], str)
            or len(body["uploadId"]) > 100
        ):
            raise AppError("Invalid upload confirmation.")
        ticket = self.repository.get("upload:" + body["uploadId"])
        job = self.get(job_id)
        if (
            not ticket
            or ticket["jobId"] != job_id
            or ticket["subject"] != subject
            or ticket["jobCreatedAt"] != job["createdAt"]
        ):
            raise AppError("Upload not found.", 404, "NOT_FOUND")
        if any(doc["id"] == body["uploadId"] for doc in job.get("attachments", [])):
            return self.public(job)
        if ticket["expiresAt"] < time.time():
            raise AppError("Upload expired. Select the file again.")
        if len(job.get("attachments", [])) >= MAX_ATTACHMENTS:
            raise AppError("Each job supports up to 10 attachments.")
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=ticket["s3Key"])
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise AppError(
                    "Upload is not complete. Retry the file upload."
                ) from None
            raise
        try:
            if (
                obj["ContentLength"] != ticket["size"]
                or obj["ContentLength"] > MAX_SIZE
            ):
                raise AppError("Uploaded file size does not match.")
            data = obj["Body"].read(MAX_SIZE + 1)
        finally:
            obj["Body"].close()
        try:
            if (
                len(data) != ticket["size"]
                or not data.startswith(b"%PDF-")
                or b"%%EOF" not in data[-2048:]
            ):
                raise ValueError("Invalid PDF")
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError("Unreadable PDF")
        except Exception:
            raise AppError("Upload a readable, non-password-protected PDF.") from None
        # Publish validated bytes under a fresh key that the browser cannot overwrite.
        key = f"job-openings/documents/{job_id}/{uuid4()}.pdf"
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/pdf",
            ServerSideEncryption="AES256",
        )
        job.setdefault("attachments", []).append(
            {
                "id": body["uploadId"],
                "category": ticket["category"],
                "fileName": ticket["fileName"],
                "size": len(data),
                "uploadedAt": datetime.now(timezone.utc).isoformat(),
                "s3Key": key,
            }
        )
        try:
            self.repository.save(job, job.get("version", 0))
        except AppError:
            self.cleanup(key)
            raise
        except Exception:
            # A timed-out write may already have committed. Keep validated bytes
            # so retrying confirmation can recover without breaking that attachment.
            audit("job_attachment_save_uncertain", status="FAILED")
            raise
        self.cleanup(ticket["s3Key"])
        return self.public(job)

    def document(self, job_id, document_id):
        self.storage_required()
        job = self.get(job_id)
        doc = next(
            (doc for doc in job.get("attachments", []) if doc["id"] == document_id),
            None,
        )
        if not doc:
            raise AppError("Attachment not found.", 404, "NOT_FOUND")
        url = self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": doc["s3Key"],
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": "attachment; filename*=UTF-8''"
                + quote(doc["fileName"], safe=""),
            },
            ExpiresIn=300,
        )
        return {"url": url}
