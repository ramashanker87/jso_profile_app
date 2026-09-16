import base64
from dataclasses import replace
import json
from unittest.mock import Mock

import boto3
from moto import mock_aws
import pytest

from conftest import event
from src.errors import AppError
from src.handlers.api import handle
from src.repositories.job_opening_repository import DynamoJobOpeningRepository, MemoryJobOpeningRepository
from src.services.job_opening_service import JobOpeningService


@pytest.fixture(params=["memory", "dynamo"])
def repository(request):
    if request.param == "memory":
        yield MemoryJobOpeningRepository()
    else:
        with mock_aws():
            table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
                TableName="job-openings", BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}])
            yield DynamoJobOpeningRepository(table)


def test_add_list_duplicate_and_delete(repository):
    service = JobOpeningService(repository)
    first = service.create({"url": " HTTPS://Example.org:443/careers/123 ", "title": "Engineer"}, "owner")
    assert first["url"] == "https://example.org/careers/123"
    assert first["title"] == "Engineer"
    assert first["createdBy"] == "owner"
    assert JobOpeningService(repository).list()["items"] == [first]
    with pytest.raises(AppError) as exc:
        service.create({"url": "https://example.org/careers/123"}, "another-user")
    assert exc.value.status == 409
    second = service.create({"url": "https://example.org/jobs/456"}, "another-user")
    assert service.list()["items"] == [second, first]
    assert second["title"] == "example.org"
    service.delete(first["id"])
    service.delete(first["id"])
    assert service.list()["items"] == [second]


@pytest.mark.parametrize("body", [None, [], {}, {"url": 123}, {"url": "javascript:alert(1)"},
    {"url": "data:text/html,hello"}, {"url": "//example.org/job"}, {"url": "https://"},
    {"url": "https://user:password@example.org/job"}, {"url": "https://example.org:bad/job"},
    {"url": "https://example.org/\njob"}, {"url": "https://example.org\\@evil.org"},
    {"url": "https://example.org/" + "a" * 4000}, {"url": "https://example.org", "title": []},
    {"url": "https://example.org", "title": "a" * 201}, {"url": "https://example.org", "createdBy": "other"}])
def test_invalid_input_does_not_create(body):
    service = JobOpeningService(MemoryJobOpeningRepository())
    with pytest.raises(AppError):
        service.create(body, "owner")
    assert service.list()["items"] == []


def test_scan_reads_all_pages():
    table = Mock()
    table.scan.side_effect = [
        {"Items": [{"id": "one"}], "LastEvaluatedKey": {"id": "one"}},
        {"Items": [{"id": "two"}]}]
    assert DynamoJobOpeningRepository(table).list() == [{"id": "one"}, {"id": "two"}]
    table.scan.assert_called_with(ConsistentRead=True, ExclusiveStartKey={"id": "one"})


def test_routes_require_approval_and_persist(runtime):
    runtime.job_openings = MemoryJobOpeningRepository()
    runtime.settings = replace(runtime.settings, required_group="approved")
    for path, method in [("/job-openings", "GET"), ("/job-openings", "POST"), ("/job-openings/" + "a" * 64, "DELETE")]:
        assert handle(event(path, method, authenticated=False), runtime)["statusCode"] == 401
        assert handle(event(path, method), runtime)["statusCode"] == 403

    def call(path="/job-openings", method="GET", body=""):
        request = event(path, method, body)
        request["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = ["approved"]
        return handle(request, runtime)

    created = call(method="POST", body=json.dumps({"url": "https://example.org/job"}))
    assert created["statusCode"] == 201
    job = json.loads(created["body"])
    assert json.loads(call()["body"])["items"] == [job]
    assert call(method="POST", body="invalid")["statusCode"] == 400
    assert call("/job-openings/invalid", "DELETE")["statusCode"] == 404
    assert call("/job-openings/" + job["id"], "DELETE")["statusCode"] == 200
    assert json.loads(call()["body"])["items"] == []


def test_base64_body_and_missing_configuration(runtime):
    assert handle(event("/job-openings"), runtime)["statusCode"] == 503
    runtime.job_openings = MemoryJobOpeningRepository()
    request = event("/job-openings", "POST", base64.b64encode(b'{"url":"https://example.org/job"}').decode())
    request["isBase64Encoded"] = True
    assert handle(request, runtime)["statusCode"] == 201
