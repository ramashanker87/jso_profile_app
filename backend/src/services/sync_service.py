from contextlib import nullcontext
from dataclasses import replace
import hashlib
import json
import re
from typing import Any, Callable

from src.config import Settings
from src.errors import AppError, DocumentError
from src.logging_utils import audit
from src.models.profile import ProfileInput, now_iso, profile_id
from src.services.neetform_parser import NeetoSubmissionMapper
from src.services.storage_service import fingerprint


class SyncService:
    def __init__(
        self, settings: Settings, profiles: Any, storage: Any, locks: Any = None, google_factory: Any = None
    ):
        self.settings, self.profiles, self.storage = settings, profiles, storage
        self.locks = locks
        self.google_factory = google_factory

    def upsert(self, source: ProfileInput) -> str:
        scope = "email:" + (source.email.strip().casefold() or source.submission_id)
        with self.locks.hold(scope) if self.locks else nullcontext():
            if source.source == "google_sheets":
                return self._upsert_member(source)
            return self._upsert(source)

    def _upsert_member(self, source: ProfileInput) -> str:
        email = source.email.strip().casefold()
        matches = sorted((p for p in self.profiles.all()
                          if p.get("email", "").strip().casefold() == email),
                         key=lambda p: (p.get("createdAt", ""), p["profileId"]))
        previous = matches[0] if matches else None
        active = source.member.get("status") == "active"
        if not active and not previous:
            return "unchanged"
        pid = previous["profileId"] if previous else profile_id("email", email)
        stamp = now_iso()
        core = dict(name=source.name, email=email, member=source.member,
                    source="google_sheets", supportRaw=source.support_raw,
                    theme=source.theme, submissionDate=source.submission_date,
                    active=active)
        digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
        unchanged = bool(previous and previous.get("memberFingerprint") == digest)
        item = {**(previous or {}), **core, "profileId": pid,
                "submissionId": source.submission_id, "memberFingerprint": digest,
                "createdAt": previous.get("createdAt", stamp) if previous else stamp,
                "updatedAt": previous.get("updatedAt", stamp) if unchanged else stamp,
                "lastSyncedAt": stamp, "syncStatus": "SUCCESS", "syncError": None}
        # Metadata remains usable when a photo is missing, private, or unsupported.
        item = self.profiles.save(item, int(previous.get("revision", 0)) if previous else 0)
        for duplicate in matches[1:]:
            self.profiles.save({**duplicate, "mergedInto": pid}, int(duplicate["revision"]))
        upload = source.member.get("fileUpload", "")
        if active and upload:
            try:
                data = self.google_factory().photo(upload)
                photo_digest = hashlib.sha256(data).hexdigest()
                if photo_digest != item.get("photoFingerprint"):
                    item["photo"] = self.storage.upload_photo(pid, data)
                    item["photoFingerprint"] = photo_digest
                    item["updatedAt"] = stamp
                    unchanged = False
            except Exception:
                item.update(syncStatus="PARTIAL", syncError="Photo unavailable. Check the uploaded file and sharing permissions.")
        elif not upload:
            item.pop("photo", None)
            item.pop("photoFingerprint", None)
        self.profiles.save(item, int(item["revision"]))
        return "failed" if item["syncStatus"] != "SUCCESS" else (
            "created" if previous is None else "unchanged" if unchanged else "updated")

    def _upsert(self, source: ProfileInput) -> str:
        pid = profile_id(self.settings.form_id, source.submission_id)
        previous = self.profiles.get(pid)
        stamp = now_iso()
        revision = int(previous.get("revision", 0)) if previous else 0
        if (
            previous
            and source.source_updated_at
            and source.source_updated_at < previous.get("sourceUpdatedAt", "")
        ):
            self.profiles.save({**previous, "lastSyncedAt": stamp}, revision)
            return "unchanged"
        core = {
            "profileId": pid,
            "submissionId": source.submission_id,
            "name": source.name,
            "email": source.email,
            "linkedinUrl": source.linkedin_url,
            "supportRaw": source.support_raw,
            "support": [
                kind
                for kind in ("time", "money")
                if re.search(r"\b" + kind + r"\b", source.support_raw, re.I)
            ],
            "theme": source.theme,
            "submissionDate": source.submission_date,
            "sourceUpdatedAt": source.source_updated_at,
            "source": "neetoform",
        }
        content_fingerprint = hashlib.sha256(
            json.dumps(core, sort_keys=True).encode()
        ).hexdigest()
        file = source.files[0] if source.files else None
        # Submission revisions are a conservative fallback when the attachment
        # has no version of its own but keeps a stable URL.
        versioned_file = (
            replace(file, version=file.version or source.source_updated_at)
            if file
            else None
        )
        file_fingerprint = fingerprint(versioned_file) if versioned_file else ""
        unchanged = bool(
            previous
            and previous.get("contentFingerprint") == content_fingerprint
            and previous.get("fileFingerprint", "") == file_fingerprint
            and previous.get("syncStatus") == "SUCCESS"
        )
        item = {
            **(previous or {}),
            **core,
            "contentFingerprint": content_fingerprint,
            "lastSyncedAt": stamp,
            "createdAt": previous["createdAt"] if previous else stamp,
            "updatedAt": previous["updatedAt"] if unchanged else stamp,
            "syncStatus": "SUCCESS" if unchanged else "PARTIAL",
            "syncError": None if unchanged else "Document synchronization is pending.",
        }
        # Commit metadata before network I/O; a failed PDF must never discard the profile.
        item = self.profiles.save(item, revision)
        downloaded = False
        try:
            if file:
                document = self.storage.existing(pid, file_fingerprint, file.name)
                if document is None:
                    document = self.storage.upload(pid, file, file_fingerprint)
                    downloaded = True
                    item["updatedAt"] = stamp
                item.update(
                    pdf=document,
                    fileFingerprint=file_fingerprint,
                    syncStatus="SUCCESS",
                    syncError=None,
                )
            else:
                # Absence in the source is never a deletion instruction.
                item.update(
                    syncStatus="PARTIAL", syncError="No profile document was supplied."
                )
        except DocumentError as error:
            item.update(
                syncStatus=(
                    "FAILED"
                    if error.code in ("FILE_TOO_LARGE", "INVALID_DOCUMENT")
                    else "PARTIAL"
                ),
                syncError=str(error),
            )
            audit(
                "document_sync",
                profileId=pid,
                submissionId=source.submission_id,
                status=item["syncStatus"],
                errorType=error.code,
            )
        except Exception:
            item.update(
                syncStatus="PARTIAL",
                syncError="Document could not be stored. Retry synchronization.",
            )
            audit(
                "document_sync",
                profileId=pid,
                submissionId=source.submission_id,
                status="PARTIAL",
                errorType="STORAGE_FAILED",
            )
        self.profiles.save(item, int(item["revision"]))
        outcome = (
            "failed"
            if item["syncStatus"] != "SUCCESS"
            else (
                "created"
                if previous is None
                else "unchanged" if unchanged and not downloaded else "updated"
            )
        )
        audit(
            "profile_sync",
            profileId=pid,
            submissionId=source.submission_id,
            operation=outcome,
            status=item["syncStatus"],
        )
        return outcome


class SyncRunner:
    """Checkpointed batches avoid API Gateway and Lambda runtime limits, without a queue."""

    def __init__(
        self,
        jobs: Any,
        service: SyncService,
        mapper: NeetoSubmissionMapper,
        neeto: Any,
        dispatch: Callable[[dict[str, Any]], None],
        finalize=None,
    ):
        self.finalize = finalize
        self.jobs, self.service, self.mapper, self.neeto, self.dispatch = (
            jobs,
            service,
            mapper,
            neeto,
            dispatch,
        )

    def _schedule(self, job: dict[str, Any]) -> None:
        self.dispatch(
            {
                "action": "sync",
                "jobId": job["jobId"],
                "generation": int(job["generation"]),
            }
        )
        # A per-job lease serializes generations. A retried predecessor repairs
        # dispatch if execution stopped between checkpoint and invocation.
        job["scheduledGeneration"] = job["generation"]
        self.jobs.save(job)

    def _complete(self, job, remaining_ms):
        if self.finalize:
            job["phase"] = "reconcile"
            self.jobs.save(job)
            if not self.finalize(job, remaining_ms):
                job["generation"] += 1
                job["status"] = "QUEUED"
                self.jobs.save(job)
                self._schedule(job)
                return
        job["status"] = "COMPLETED"
        self.jobs.save(job)

    def batch(
        self,
        job_id: str,
        generation: int,
        remaining_ms: Callable[[], int] = lambda: 900000,
    ) -> None:
        job = self.jobs.get(job_id)
        if not job or job["status"] in ("COMPLETED", "FAILED"):
            return
        if int(job["generation"]) != generation:
            if int(job.get("scheduledGeneration", -1)) < int(job["generation"]):
                self._schedule(job)
            return
        job["status"] = "RUNNING"
        self.jobs.save(job)
        try:
            if job.get("phase") == "reconcile":
                self._complete(job, remaining_ms)
                return
            entries, total = self.neeto.page(int(job["pageNumber"]), 20)
            offset = int(job["offset"])
            processed_batch = 0
            while (
                offset < len(entries)
                and processed_batch < 8
                and remaining_ms() > 100000
            ):
                try:
                    outcome = self.service.upsert(self.mapper.parse(entries[offset]))
                except AppError as error:
                    outcome = "failed"
                    audit(
                        "profile_sync",
                        jobId=job_id,
                        status="FAILED",
                        errorType=error.code,
                    )
                job[outcome] += 1
                job["processed"] += 1
                offset += 1
                processed_batch += 1
                job["offset"] = offset
                self.jobs.save(job)
            complete_page = offset >= len(entries)
            if not complete_page and processed_batch == 0:
                raise AppError(
                    "The source response left insufficient processing time. Retry synchronization.",
                    503,
                    "TIME_BUDGET",
                )
            reached_total = (
                total is not None
                and (int(job["pageNumber"]) - 1) * 20 + offset >= total
            )
            if not entries or complete_page and reached_total:
                self._complete(job, remaining_ms)
                return
            if complete_page:
                job["pageNumber"] += 1
                job["offset"] = 0
            if int(job["pageNumber"]) > 10000:
                raise AppError(
                    "Neeto API pagination limit reached.", 502, "PAGINATION_LIMIT"
                )
            job["generation"] += 1
            job["status"] = "QUEUED"
            self.jobs.save(job)
        except AppError as error:
            job.update(status="FAILED", error=str(error))
            self.jobs.save(job)
            return
        self._schedule(job)
