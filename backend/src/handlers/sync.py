from typing import Any
from src.errors import AppError


def start(runtime: Any, members=False) -> dict[str, Any]:
    if members:
        runtime.member_source()
    else:
        runtime.neeto()  # Fail clearly before creating a job if credentials are absent.
    jobs = runtime.member_jobs if members else runtime.jobs
    if jobs is None:
        raise AppError("Member sync is not configured.", 503, "NOT_CONFIGURED")
    job = jobs.start()
    try:
        runtime.dispatch({"action": "member_sync" if members else "sync", "jobId": job["jobId"], "generation": 0})
    except Exception:
        job.update(
            status="FAILED", error="Unable to start synchronization. Retry shortly."
        )
        jobs.save(job)
        raise AppError(job["error"], 503, "SYNC_UNAVAILABLE") from None
    return public_job(job)


def public_job(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not job:
        return None
    return {
        key: job.get(key)
        for key in (
            "jobId",
            "status",
            "processed",
            "created",
            "updated",
            "unchanged",
            "failed",
            "deleted",
            "createdAt",
            "updatedAt",
            "error",
        )
    }
