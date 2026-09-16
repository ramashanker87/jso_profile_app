from copy import deepcopy
import time
from typing import Any
from uuid import uuid4
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from src.errors import AppError
from src.models.profile import now_iso


def new_job(kind="profiles") -> dict[str, Any]:
    return {
        "jobId": str(uuid4()),
        "kind": kind,
        "status": "QUEUED",
        "pageNumber": 1,
        "offset": 0,
        "generation": 0,
        "scheduledGeneration": -1,
        "processed": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
        "deleted": 0,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
        "error": None,
    }


class DynamoJobRepository:
    def __init__(self, table: Any, client: Any, kind="profiles"):
        self.table, self.client, self.kind = table, client, kind
        self.state_key = "STATE" if kind == "profiles" else "STATE#" + kind

    def start(self) -> dict[str, Any]:
        job = new_job(self.kind)
        serialize = TypeSerializer().serialize
        try:
            self.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": self.table.name,
                            "Item": {k: serialize(v) for k, v in job.items()},
                            "ConditionExpression": "attribute_not_exists(jobId)",
                        }
                    },
                    {
                        "Update": {
                            "TableName": self.table.name,
                            "Key": {"jobId": {"S": self.state_key}},
                            "UpdateExpression": "SET activeJobId = :id, activeUntil = :until",
                            "ConditionExpression": "attribute_not_exists(activeUntil) OR activeUntil < :now",
                            "ExpressionAttributeValues": {
                                ":id": {"S": job["jobId"]},
                                ":until": {"N": str(int(time.time()) + 1800)},
                                ":now": {"N": str(int(time.time()))},
                            },
                        }
                    },
                ]
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException":
                raise AppError(
                    "A sync is already running. Check its status.", 409, "SYNC_RUNNING"
                ) from None
            raise
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"jobId": job_id}, ConsistentRead=True).get("Item")
        if item and job_id != self.state_key and item.get("kind", "profiles") != self.kind:
            return None
        return item

    def latest(self) -> dict[str, Any] | None:
        state = self.get(self.state_key) or {}
        job = self.get(state["activeJobId"]) if state.get("activeJobId") else None
        if (
            job
            and job["status"] in ("QUEUED", "RUNNING")
            and int(state.get("activeUntil", 0)) < time.time()
        ):
            return {
                **job,
                "status": "FAILED",
                "error": "Sync stopped unexpectedly. You can start a new sync.",
            }
        return job

    def save(self, job: dict[str, Any]) -> None:
        job["updatedAt"] = now_iso()
        self.table.put_item(Item=job)
        until = (
            0 if job["status"] in ("COMPLETED", "FAILED") else int(time.time()) + 1800
        )
        try:
            self.table.update_item(
                Key={"jobId": self.state_key},
                UpdateExpression="SET activeUntil = :until",
                ConditionExpression="activeJobId = :id",
                ExpressionAttributeValues={":until": until, ":id": job["jobId"]},
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise


class MemoryJobRepository:
    def __init__(self, kind="profiles"):
        self.kind = kind
        self.items: dict[str, dict[str, Any]] = {}
        self.active: str | None = None

    def start(self) -> dict[str, Any]:
        if self.active and self.items[self.active]["status"] in ("QUEUED", "RUNNING"):
            raise AppError("A sync is already running.", 409, "SYNC_RUNNING")
        job = new_job(self.kind)
        self.active = job["jobId"]
        self.save(job)
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        return deepcopy(self.items.get(job_id))

    def latest(self) -> dict[str, Any] | None:
        return self.get(self.active) if self.active else None

    def save(self, job: dict[str, Any]) -> None:
        job["updatedAt"] = now_iso()
        self.items[job["jobId"]] = deepcopy(job)
