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
            items.extend(result.get("Items", []))
            if not result.get("LastEvaluatedKey"):
                return items
            arguments["ExclusiveStartKey"] = result["LastEvaluatedKey"]

    def create(self, item):
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AppError("This job-opening link has already been added.", 409, "CONFLICT") from None
            raise

    def delete(self, job_id):
        # Idempotent: two approved members can close the same listing safely.
        self.table.delete_item(Key={"id": job_id})


class MemoryJobOpeningRepository:
    def __init__(self):
        self.items = {}
        self.lock = Lock()

    def list(self):
        with self.lock:
            return deepcopy(list(self.items.values()))

    def create(self, item):
        with self.lock:
            if item["id"] in self.items:
                raise AppError("This job-opening link has already been added.", 409, "CONFLICT")
            self.items[item["id"]] = deepcopy(item)

    def delete(self, job_id):
        with self.lock:
            self.items.pop(job_id, None)
