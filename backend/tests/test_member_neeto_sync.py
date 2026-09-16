import copy
import json
from dataclasses import replace
from unittest.mock import Mock
import boto3
from moto import mock_aws
import pytest
from conftest import event
from src.errors import AppError
from src.handlers.api import handle
from src.handlers.worker import handle as worker_handle
from src.repositories.job_repository import DynamoJobRepository, MemoryJobRepository
from src.services.member_neeto_service import MemberSource, MemberSyncService
from src.config import Settings


def submission(n, email=None, status="approved", date="2026-01-01T00:00:00Z"):
    return {"id": str(n), "created_at": date,
            "field_values": [{"field_id": "status-field", "data": {"values": [status]}}],
            "responses": [
                {"slug": "full-name", "value": "Example Member"},
                {"slug": "email-address", "value": email or f"member{n}@example.org"},
                {"slug": "phone-number", "value": {"country_name": "Example", "value": "+00123"}},
                {"slug": "address-2", "value": {"address": [{"label": "City", "content": "Example City"}]}},
                {"slug": "unique-id", "value": f"JSO-{n}"},
            ]}


def source(items):
    client = Mock()
    client.page.side_effect = lambda n, size: (items[(n-1)*size:n*size], len(items))
    return MemberSource(client, "member-form", "status-field", "approved")


def test_filter_across_all_pages_and_normalize_nested_fields():
    items = [submission(n, status="pending") for n in range(105)]
    items[-1] = submission(104, email=" Person@Example.org ")
    src = source(items)
    rows, count = src.page(1, 20)
    assert count == 1 and src.client.page.call_count == 2
    assert rows[0]["row"]["Email"] == "person@example.org"
    assert rows[0]["row"]["Phone"] == "+00123"
    assert rows[0]["row"]["Address"] == "Example City"
    assert src.page(2, 20) == ([], 1)


def test_only_configured_status_field_can_select_a_member():
    item = submission(1, status="pending")
    item["field_values"].append({"field_id": "unrelated", "data": {"values": ["approved"]}})
    assert source([item]).rows() == []


def test_duplicate_emails_merge_latest_selected_and_preserve_earliest_date():
    old = submission(1, email="PERSON@example.org")
    new = submission(2, email="person@example.org", date="2026-02-01T00:00:00Z")
    new["responses"].append({"slug": "type-a-question-2", "value": "Sweden"})
    rows = source([new, old, submission(3, email="person@example.org", status="pending")]).rows()
    assert len(rows) == 1
    row = rows[0]["row"]
    assert row["Country"] == "Sweden" and row["Unique ID"] == "JSO-2"
    assert row["Number of Submissions"] == "2"
    assert row["Submitted On (Earliest)"] == old["created_at"]


def test_invalid_selected_email_fails_before_returning_any_rows():
    with pytest.raises(AppError, match="invalid email"):
        source([submission(1), submission(2, email="invalid")]).rows()
    assert source([submission(2, email="invalid", status="pending")]).rows() == []


@mock_aws
def test_member_updates_are_idempotent_and_preserve_unrelated_fields_and_photo():
    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.create_table(TableName="members", KeySchema=[{"AttributeName": "Email", "KeyType": "HASH"}], AttributeDefinitions=[{"AttributeName": "Email", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
    service = MemberSyncService(table, Mock(), Settings())
    row = source([submission(1)]).rows()[0]
    assert service.upsert(row) == "created"
    table.update_item(Key={"Email": "member1@example.org"}, UpdateExpression="SET LegacyField = :v, Photo = :p", ExpressionAttributeValues={":v": "keep", ":p": {"s3Key": "profiles/legacy/photo.jpg"}})
    assert service.upsert(row) == "unchanged"
    updated = copy.deepcopy(row)
    updated["row"]["Country"] = "Sweden"
    assert service.upsert(updated) == "updated"
    item = table.get_item(Key={"Email": "member1@example.org"})["Item"]
    assert item["LegacyField"] == "keep" and item["Photo"]["s3Key"].endswith("photo.jpg")
    assert item["Country"] == "Sweden" and table.scan()["Count"] == 1


@mock_aws
def test_member_and_profile_jobs_run_independently_and_cannot_read_each_other():
    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.create_table(TableName="jobs", KeySchema=[{"AttributeName": "jobId", "KeyType": "HASH"}], AttributeDefinitions=[{"AttributeName": "jobId", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")
    profiles = DynamoJobRepository(table, boto3.client("dynamodb", region_name="us-east-1"))
    members = DynamoJobRepository(table, boto3.client("dynamodb", region_name="us-east-1"), kind="members")
    p, m = profiles.start(), members.start()
    assert profiles.latest()["jobId"] == p["jobId"]
    assert members.latest()["jobId"] == m["jobId"]
    assert profiles.get(m["jobId"]) is None and members.get(p["jobId"]) is None
    with pytest.raises(AppError):
        members.start()
    m["status"] = "COMPLETED"
    members.save(m)
    members.start()
    with pytest.raises(AppError):
        profiles.start()


def test_member_sync_api_auth_and_worker_checkpoints_are_separate(runtime):
    runtime.member_jobs = MemoryJobRepository(kind="members")
    runtime.member_source = Mock(return_value=source([submission(n) for n in range(142)]))
    service = Mock()
    service.upsert.return_value = "created"
    runtime.member_sync_service = Mock(return_value=service)
    assert handle(event('/members/sync', 'POST', authenticated=False), runtime)['statusCode'] == 401
    response = handle(event('/members/sync', 'POST'), runtime)
    assert response['statusCode'] == 202
    job = json.loads(response['body'])
    payload = runtime.dispatch.call_args.args[0]
    assert payload['action'] == 'member_sync'
    for _ in range(30):
        worker_handle(payload, None, runtime)
        if runtime.member_jobs.latest()['status'] == 'COMPLETED': break
        payload = runtime.dispatch.call_args.args[0]
        assert payload['action'] == 'member_sync'
    assert runtime.member_jobs.latest()['processed'] == 142
    assert runtime.jobs.latest() is None
    assert runtime.member_jobs.latest()['status'] == 'COMPLETED'
    assert service.upsert.call_count == 142
    assert handle(event('/members/sync/' + job['jobId']), runtime)['statusCode'] == 200
    assert handle(event('/members/sync/STATE#members'), runtime)['statusCode'] == 404


def test_unfiltered_members_include_every_status_and_missing_status():
    items = [submission(1), submission(2, status="pending"), submission(3, status="rejected")]
    items[2]["field_values"] = []
    client = Mock()
    client.page.return_value = (items, 3)
    rows = MemberSource(client, "member-form", "", "").rows()
    assert len(rows) == 3
    assert {row["row"]["Email"] for row in rows} == {f"member{n}@example.org" for n in (1, 2, 3)}


@pytest.mark.parametrize("field,value", [("field", ""), ("", "value")])
def test_partial_status_configuration_is_rejected(field, value):
    with pytest.raises(AppError, match="both status filter"):
        MemberSource(Mock(), "member-form", field, value)
