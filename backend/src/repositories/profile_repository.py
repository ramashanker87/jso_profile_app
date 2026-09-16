from copy import deepcopy
from typing import Any, Protocol
from botocore.exceptions import ClientError
from src.errors import AppError


class ProfileRepository(Protocol):
    def get(self, profile_id: str) -> dict[str, Any] | None: ...
    def all(self) -> list[dict[str, Any]]: ...
    def save(self, item: dict[str, Any], revision: int) -> dict[str, Any]: ...


class DynamoProfileRepository:
    def __init__(self, table: Any):
        self.table = table

    def get(self, profile_id: str) -> dict[str, Any] | None:
        return self.table.get_item(
            Key={"profileId": profile_id}, ConsistentRead=True
        ).get("Item")

    def all(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        arguments: dict[str, Any] = {"ConsistentRead": True}
        while True:
            page = self.table.scan(**arguments)
            items.extend(page.get("Items", []))
            if not page.get("LastEvaluatedKey"):
                return items
            arguments["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def save(self, item: dict[str, Any], revision: int) -> dict[str, Any]:
        saved = {**item, "revision": revision + 1}
        arguments: dict[str, Any] = {
            "Item": saved,
            "ConditionExpression": (
                "attribute_not_exists(profileId)"
                if revision == 0
                else "revision = :revision"
            ),
        }
        if revision:
            arguments["ExpressionAttributeValues"] = {":revision": revision}
        try:
            self.table.put_item(**arguments)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AppError(
                    "Profile changed during synchronization. Retry.", 409, "CONFLICT"
                ) from None
            raise
        return saved


class MemoryProfileRepository:
    def __init__(self, items: list[dict[str, Any]] | None = None):
        self.items = {item["profileId"]: deepcopy(item) for item in items or []}

    def get(self, profile_id: str) -> dict[str, Any] | None:
        return deepcopy(self.items.get(profile_id))

    def all(self) -> list[dict[str, Any]]:
        return deepcopy(list(self.items.values()))

    def save(self, item: dict[str, Any], revision: int) -> dict[str, Any]:
        if int(self.items.get(item["profileId"], {}).get("revision", 0)) != revision:
            raise AppError(
                "Profile changed during synchronization. Retry.", 409, "CONFLICT"
            )
        saved = {**deepcopy(item), "revision": revision + 1}
        self.items[item["profileId"]] = saved
        return deepcopy(saved)
