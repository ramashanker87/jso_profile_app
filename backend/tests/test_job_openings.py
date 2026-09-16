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
from src.repositories.job_opening_repository import (
    DynamoJobOpeningRepository,
    MemoryJobOpeningRepository,
)
from src.services.job_opening_service import JobOpeningService


@pytest.fixture(params=["memory", "dynamo"])
def repository(request):
    if request.param == "memory":
        yield MemoryJobOpeningRepository()
    else:
        with mock_aws():
            table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
                TableName="job-openings",
                BillingMode="PAY_PER_REQUEST",
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            )
            yield DynamoJobOpeningRepository(table)


def test_add_list_duplicate_and_delete(repository):
    service = JobOpeningService(repository)
    first = service.create(
        {"url": " HTTPS://Example.org:443/careers/123 ", "title": "Engineer"}, "owner"
    )
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


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"url": 123},
        {"url": "javascript:alert(1)"},
        {"url": "data:text/html,hello"},
        {"url": "//example.org/job"},
        {"url": "https://"},
        {"url": "https://user:password@example.org/job"},
        {"url": "https://example.org:bad/job"},
        {"url": "https://example.org/\njob"},
        {"url": "https://example.org\\@evil.org"},
        {"url": "https://example.org/" + "a" * 4000},
        {"url": "https://example.org", "title": []},
        {"url": "https://example.org", "title": "a" * 201},
        {"url": "https://example.org", "createdBy": "other"},
    ],
)
def test_invalid_input_does_not_create(body):
    service = JobOpeningService(MemoryJobOpeningRepository())
    with pytest.raises(AppError):
        service.create(body, "owner")
    assert service.list()["items"] == []


def test_scan_reads_all_pages():
    table = Mock()
    table.scan.side_effect = [
        {"Items": [{"id": "one"}], "LastEvaluatedKey": {"id": "one"}},
        {"Items": [{"id": "two"}]},
    ]
    assert DynamoJobOpeningRepository(table).list() == [{"id": "one"}, {"id": "two"}]
    table.scan.assert_called_with(ConsistentRead=True, ExclusiveStartKey={"id": "one"})


def test_routes_require_approval_and_persist(runtime):
    runtime.job_openings = MemoryJobOpeningRepository()
    runtime.settings = replace(runtime.settings, required_group="approved")
    for path, method in [
        ("/job-openings", "GET"),
        ("/job-openings", "POST"),
        ("/job-openings/" + "a" * 64, "DELETE"),
    ]:
        assert (
            handle(event(path, method, authenticated=False), runtime)["statusCode"]
            == 401
        )
        assert handle(event(path, method), runtime)["statusCode"] == 403

    def call(path="/job-openings", method="GET", body=""):
        request = event(path, method, body)
        request["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = [
            "approved"
        ]
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
    request = event(
        "/job-openings",
        "POST",
        base64.b64encode(b'{"url":"https://example.org/job"}').decode(),
    )
    request["isBase64Encoded"] = True
    assert handle(request, runtime)["statusCode"] == 201


def test_description_and_legacy_records(repository):
    service = JobOpeningService(repository)
    created = service.create(
        {
            "url": "https://example.org/description",
            "description": " Summary\nRequirements ",
        },
        "owner",
    )
    assert created["description"] == "Summary\nRequirements"
    assert created["attachments"] == []
    assert service.list()["items"][0]["description"] == created["description"]
    for value in [None, [], 123, "a" * 2001]:
        with pytest.raises(AppError):
            service.create(
                {"url": "https://example.org/invalid", "description": value}, "owner"
            )
    legacy = {
        "id": "b" * 64,
        "url": "https://example.org/legacy",
        "title": "Legacy",
        "createdAt": "2020",
    }
    repository.create(legacy)
    assert service.list()["items"][-1]["attachments"] == []
    assert service.list()["items"][-1]["description"] == ""


@pytest.fixture
def attachments(repository):
    from pathlib import Path

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="job-documents")
        service = JobOpeningService(repository, s3, "job-documents")
        job = service.create({"url": "https://example.org/attachments"}, "owner")
        pdf = (Path(__file__).parent / "fixtures/sample-profile.pdf").read_bytes()
        yield service, s3, job, pdf


def stage(attachments, data=None, category="candidate-profile"):
    service, s3, job, pdf = attachments
    data = pdf if data is None else data
    ticket = service.begin_upload(
        job["id"],
        {"category": category, "fileName": "profile.pdf", "size": len(data)},
        "owner",
    )
    s3.put_object(Bucket="job-documents", Key=ticket["fields"]["key"], Body=data)
    return ticket


def test_private_attachment_upload_download_retry_and_delete(attachments):
    from urllib.parse import parse_qs, urlparse

    service, s3, job, pdf = attachments
    ticket = stage(attachments)
    policy = json.loads(base64.b64decode(ticket["fields"]["policy"]))
    assert ["content-length-range", len(pdf), len(pdf)] in policy["conditions"]
    assert {"x-amz-server-side-encryption": "AES256"} in policy["conditions"]
    # Upload tickets must never be shown as job listings.
    assert service.list()["items"] == [job]
    saved = service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    doc = saved["attachments"][0]
    assert doc["category"] == "candidate-profile"
    assert doc["size"] == len(pdf)
    assert "s3Key" not in json.dumps(saved)
    assert (
        service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
        == saved
    )
    # Replaying the signed POST may change staging, never the published bytes.
    s3.put_object(Bucket="job-documents", Key=ticket["fields"]["key"], Body=b"replaced")
    stored = service.repository.get(job["id"])["attachments"][0]
    assert (
        s3.get_object(Bucket="job-documents", Key=stored["s3Key"])["Body"].read() == pdf
    )
    link = service.document(job["id"], doc["id"])["url"]
    assert parse_qs(urlparse(link).query)["response-content-disposition"] == [
        "attachment; filename*=UTF-8''profile.pdf"
    ]
    with pytest.raises(AppError):
        service.document(job["id"], "unknown")
    service.delete(job["id"])
    with pytest.raises(s3.exceptions.NoSuchKey):
        s3.get_object(Bucket="job-documents", Key=stored["s3Key"])
    with pytest.raises(AppError):
        service.document(job["id"], doc["id"])


@pytest.mark.parametrize(
    "changes",
    [
        {"category": "invalid"},
        {"category": []},
        {"fileName": "../test.pdf"},
        {"fileName": "test\n.pdf"},
        {"fileName": "test.docx"},
        {"fileName": "a" * 181 + ".pdf"},
        {"size": 0},
        {"size": True},
        {"size": 20 * 1024 * 1024 + 1},
    ],
)
def test_invalid_upload_metadata(attachments, changes):
    service, _, job, _ = attachments
    with pytest.raises(AppError):
        service.begin_upload(
            job["id"],
            {"category": "job-profile", "fileName": "job.pdf", "size": 100, **changes},
            "owner",
        )


def test_ticket_ownership_expiry_and_job_identity(attachments, monkeypatch):
    service, _, job, _ = attachments
    ticket = stage(attachments)
    body = {"uploadId": ticket["uploadId"]}
    with pytest.raises(AppError, match="not found"):
        service.finish_upload(job["id"], body, "someone-else")
    other = service.create({"url": "https://example.org/other"}, "owner")
    with pytest.raises(AppError, match="not found"):
        service.finish_upload(other["id"], body, "owner")
    with monkeypatch.context() as context:
        context.setattr(
            "src.services.job_opening_service.time.time", lambda: 9999999999
        )
        with pytest.raises(AppError, match="expired"):
            service.finish_upload(job["id"], body, "owner")
    service.delete(job["id"])
    service.create({"url": job["url"]}, "owner")
    with pytest.raises(AppError, match="not found"):
        service.finish_upload(job["id"], body, "owner")


@pytest.mark.parametrize("kind", ["fake", "encrypted", "missing", "wrong-size"])
def test_rejects_invalid_file_bytes(attachments, kind):
    import io
    from pypdf import PdfWriter

    service, s3, job, pdf = attachments
    data = pdf
    if kind == "fake":
        data = b"%PDF-not-really-a-pdf\n%%EOF"
    if kind == "encrypted":
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("password")
        output = io.BytesIO()
        writer.write(output)
        data = output.getvalue()
    ticket = stage(attachments, data)
    if kind == "missing":
        s3.delete_object(Bucket="job-documents", Key=ticket["fields"]["key"])
    if kind == "wrong-size":
        s3.put_object(
            Bucket="job-documents", Key=ticket["fields"]["key"], Body=b"short"
        )
    with pytest.raises(AppError):
        service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    assert service.list()["items"][0]["attachments"] == []
    assert not s3.list_objects_v2(
        Bucket="job-documents", Prefix="job-openings/documents/"
    ).get("Contents")


def test_concurrent_save_and_delete_cannot_overwrite_or_resurrect(repository):
    service = JobOpeningService(repository)
    job = service.create({"url": "https://example.org/concurrent"}, "owner")
    repository.save({**job, "description": "new"}, 0)
    with pytest.raises(AppError):
        repository.save({**job, "description": "stale"}, 0)
    assert repository.get(job["id"])["description"] == "new"
    service.delete(job["id"])
    with pytest.raises(AppError):
        repository.save(job, 0)
    service.create({"url": job["url"]}, "owner")
    with pytest.raises(AppError):
        repository.save(job, 0)


def test_concurrent_upload_failure_cleans_published_copy_and_allows_retry(
    attachments, monkeypatch
):
    service, s3, job, _ = attachments
    ticket = stage(attachments)
    with monkeypatch.context() as context:
        context.setattr(
            service.repository,
            "save",
            Mock(side_effect=AppError("Conflict", 409, "CONFLICT")),
        )
        with pytest.raises(AppError):
            service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    assert not s3.list_objects_v2(
        Bucket="job-documents", Prefix="job-openings/documents/"
    ).get("Contents")
    saved = service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    assert len(saved["attachments"]) == 1


def test_attachment_limit_checked_again_at_confirmation(attachments):
    service, _, job, _ = attachments
    ticket = stage(attachments)
    job["attachments"] = [{"id": str(n)} for n in range(10)]
    service.repository.save(job, 0)
    with pytest.raises(AppError, match="10 attachments"):
        service.begin_upload(
            job["id"],
            {"category": "job-profile", "fileName": "job.pdf", "size": 100},
            "owner",
        )
    with pytest.raises(AppError, match="10 attachments"):
        service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")


def test_attachment_routes_authorization_and_local_unavailable(runtime):
    runtime.job_openings = MemoryJobOpeningRepository()
    runtime.settings = replace(runtime.settings, required_group="approved")
    for path, method in [
        ("/job-openings/" + "a" * 64 + "/upload", "POST"),
        ("/job-openings/" + "a" * 64 + "/upload/complete", "POST"),
        ("/job-openings/" + "a" * 64 + "/attachments/file", "GET"),
    ]:
        assert (
            handle(event(path, method, "{}", authenticated=False), runtime)[
                "statusCode"
            ]
            == 401
        )
        assert handle(event(path, method, "{}"), runtime)["statusCode"] == 403
    service = JobOpeningService(runtime.job_openings)
    assert service.list()["uploadsEnabled"] is False
    with pytest.raises(AppError) as error:
        service.begin_upload("a" * 64, {}, "owner")
    assert error.value.status == 503


def test_uncertain_committed_save_preserves_file_and_retry_is_idempotent(
    attachments, monkeypatch
):
    service, s3, job, pdf = attachments
    ticket = stage(attachments)
    original_save = service.repository.save

    def committed_but_lost_response(item, version):
        original_save(item, version)
        raise TimeoutError("Response lost after commit")

    with monkeypatch.context() as context:
        context.setattr(service.repository, "save", committed_but_lost_response)
        with pytest.raises(TimeoutError):
            service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    saved = service.finish_upload(job["id"], {"uploadId": ticket["uploadId"]}, "owner")
    assert len(saved["attachments"]) == 1
    doc = service.repository.get(job["id"])["attachments"][0]
    assert s3.get_object(Bucket="job-documents", Key=doc["s3Key"])["Body"].read() == pdf


def test_attachment_routes_work_for_approved_user(attachments, runtime):
    service, s3, job, pdf = attachments
    runtime.job_openings = service.repository
    runtime.storage.client = s3
    runtime.storage.bucket = "job-documents"
    runtime.settings = replace(runtime.settings, required_group="approved")

    def call(path, method="GET", body=None):
        request = event(path, method, json.dumps(body) if body is not None else "")
        request["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = [
            "approved"
        ]
        result = handle(request, runtime)
        assert result["statusCode"] == 200, result
        return json.loads(result["body"])

    prefix = "/job-openings/" + job["id"]
    ticket = call(
        prefix + "/upload",
        "POST",
        {"category": "job-profile", "fileName": "job.pdf", "size": len(pdf)},
    )
    s3.put_object(Bucket="job-documents", Key=ticket["fields"]["key"], Body=pdf)
    saved = call(prefix + "/upload/complete", "POST", {"uploadId": ticket["uploadId"]})
    assert saved["attachments"][0]["category"] == "job-profile"
    assert call(prefix + "/attachments/" + saved["attachments"][0]["id"])[
        "url"
    ].startswith("https://")
