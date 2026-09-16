"""Short worker leases protect fixed-key documents without reserved concurrency."""

from contextlib import contextmanager
import time
from typing import Any, Iterator
from uuid import uuid4
from botocore.exceptions import ClientError


class LockBusy(RuntimeError):
    """Let native Lambda asynchronous delivery retry a contended operation."""


class DynamoLockRepository:
    def __init__(self, table: Any, lease_seconds: int = 130):
        # Worker timeout is 120s. A lease outlives its owner even after a timeout,
        # but expires before Lambda's final retry (normally around three minutes).
        self.table = table
        self.lease_seconds = lease_seconds

    @contextmanager
    def hold(self, scope: str) -> Iterator[None]:
        owner = str(uuid4())
        key = {"jobId": "LOCK#" + scope}
        try:
            self.table.update_item(
                Key=key,
                UpdateExpression="SET lockOwner = :owner, lockUntil = :until",
                ConditionExpression="attribute_not_exists(lockUntil) OR lockUntil < :now",
                ExpressionAttributeValues={
                    ":owner": owner,
                    ":until": int(time.time()) + self.lease_seconds,
                    ":now": int(time.time()),
                },
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise LockBusy("Synchronization is busy; retry required.") from None
            raise
        try:
            yield
        finally:
            try:
                self.table.update_item(
                    Key=key,
                    UpdateExpression="SET lockUntil = :released",
                    ConditionExpression="lockOwner = :owner",
                    ExpressionAttributeValues={":owner": owner, ":released": 0},
                )
            except ClientError as error:
                if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
