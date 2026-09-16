from contextlib import nullcontext
from typing import Any
from src.errors import AppError
from src.logging_utils import audit
from src.models.profile import ProfileInput
from src.runtime import aws_runtime
from src.services.sync_service import SyncRunner


def handle(event: dict[str, Any], context: Any, runtime: Any) -> None:
    scope = "job:" + str(event.get("jobId", ""))
    lock = (
        runtime.locks.hold(scope)
        if runtime.locks and event.get("action") in ("sync", "member_sync")
        else nullcontext()
    )
    with lock:
        process(event, context, runtime)


def process(event: dict[str, Any], context: Any, runtime: Any) -> None:
    if event.get("action") == "webhook" and runtime.settings.google_sheet_id:
        return
    if event.get("action") == "webhook":
        runtime.sync_service().upsert(ProfileInput.from_dict(event["profile"]))
    elif event.get("action") in ("sync", "member_sync"):
        members = event["action"] == "member_sync"
        jobs = runtime.member_jobs if members else runtime.jobs
        try:
            client = runtime.member_source() if members else runtime.neeto()
        except AppError as error:
            job = jobs.get(event["jobId"])
            if job:
                job.update(status="FAILED", error=str(error))
                jobs.save(job)
            return
        service = runtime.member_sync_service() if members else runtime.sync_service()
        SyncRunner(
            jobs,
            service,
            client if members else runtime.sync_mapper(),
            client,
            (lambda event: runtime.dispatch({**event, "action": "member_sync"})) if members else runtime.dispatch,
            finalize=(lambda job, remaining: service.reconcile(client, job, jobs, remaining)) if members else None,
        ).batch(
            event["jobId"],
            int(event["generation"]),
            context.get_remaining_time_in_millis if context else lambda: 900000,
        )
    else:
        raise AppError("Unknown internal synchronization event.")


def lambda_handler(event: dict[str, Any], context: Any) -> None:
    try:
        handle(event, context, aws_runtime())
    except Exception as error:
        audit("worker_error", status="FAILED", errorType=type(error).__name__)
        # AWS retries async invocations. Only a safe message reaches its exception log.
        raise RuntimeError("Synchronization worker failed; retry scheduled.") from None
