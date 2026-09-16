from copy import deepcopy
from threading import Lock

from botocore.exceptions import ClientError
from src.errors import AppError


class DynamoJobOpeningRepository:
    def __init__(self, table):
        self.table = table

    def list(self):
        items = []
        arguments = {"ConsistentRead": True}
        while True:
            result = self.table.scan(**arguments)
            items.extend(
                item
                for item in result.get("Items", [])
                if not item["id"].startswith("upload:")
            )
            if not result.get("LastEvaluatedKey"):
                return items
            arguments["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    def create(self, item):
        try:
            self.table.put_item(
                Item=item, ConditionExpression="attribute_not_exists(id)"
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AppError(
                    "This job-opening link has already been added.", 409, "CONFLICT"
                ) from None
            raise

    def get(self, item_id):
        return self.table.get_item(Key={"id": item_id}, ConsistentRead=True).get("Item")

    def save(self, item, version):
        try:
            self.table.put_item(
                Item={**item, "version": version + 1},
                ConditionExpression="createdAt = :created AND (attribute_not_exists(#v) OR #v = :v)",
                ExpressionAttributeNames={"#v": "version"},
                ExpressionAttributeValues={
                    ":created": item["createdAt"],
                    ":v": version,
                },
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AppError(
                    "This job changed. Retry the attachment upload.", 409, "CONFLICT"
                ) from None
            raise

    def delete(self, job_id):
        # Idempotent: two approved members can close the same listing safely.
        return self.table.delete_item(Key={"id": job_id}, ReturnValues="ALL_OLD").get(
            "Attributes"
        )


class MemoryJobOpeningRepository:
    def __init__(self):
        self.items = {}
        self.lock = Lock()

    def list(self):
        with self.lock:
            return deepcopy(
                [
                    item
                    for item in self.items.values()
                    if not item["id"].startswith("upload:")
                ]
            )

    def create(self, item):
        with self.lock:
            if item["id"] in self.items:
                raise AppError(
                    "This job-opening link has already been added.", 409, "CONFLICT"
                )
            self.items[item["id"]] = deepcopy(item)

    def get(self, item_id):
        with self.lock:
            return deepcopy(self.items.get(item_id))

    def save(self, item, version):
        with self.lock:
            current = self.items.get(item["id"])
            if (
                not current
                or current["createdAt"] != item["createdAt"]
                or current.get("version", 0) != version
            ):
                raise AppError(
                    "This job changed. Retry the attachment upload.", 409, "CONFLICT"
                )
            self.items[item["id"]] = deepcopy({**item, "version": version + 1})

    def delete(self, job_id):
        with self.lock:
            return self.items.pop(job_id, None)
