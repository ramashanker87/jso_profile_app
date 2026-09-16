from unittest.mock import Mock
import boto3
from moto import mock_aws
import pytest
from src.errors import AppError
from src.config import Settings
from src.repositories.job_repository import MemoryJobRepository
from src.services.member_neeto_service import MemberSource, MemberSyncService
from src.services.sync_service import SyncRunner
from test_member_neeto_sync import submission, source


@pytest.fixture
def table():
    with mock_aws():
        db = boto3.resource("dynamodb", region_name="us-east-1")
        yield db.create_table(TableName="members", KeySchema=[{"AttributeName": "Email", "KeyType": "HASH"}], AttributeDefinitions=[{"AttributeName": "Email", "AttributeType": "S"}], BillingMode="PAY_PER_REQUEST")


def stored(table, email, form="member-form"):
    row = {"Email": email, "Full Name": "Example", "LastSyncedAt": "2026-01-01", "NeetoFingerprint": "fp"}
    if form:
        row["NeetoFormId"] = form
    table.put_item(Item=row)


def reconciliation(table, items):
    src = source(items)
    jobs = MemoryJobRepository("members")
    job = jobs.start()
    service = MemberSyncService(table, Mock(), Settings())
    return service, src, job, jobs


def test_delete_absent_managed_members_only_and_keep_duplicate_email(table):
    stored(table, "removed@example.org")
    stored(table, "keep@example.org")
    stored(table, "other@example.org", "other-form")
    stored(table, "manual@example.org", None)
    service, src, job, jobs = reconciliation(table, [submission(2, email="keep@example.org")])
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert job["deleted"] == 1
    assert {i["Email"] for i in table.scan()["Items"]} == {"keep@example.org", "other@example.org", "manual@example.org"}
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert job["deleted"] == 1  # Retry does not double-count an already deleted member.


def test_valid_empty_form_removes_all_managed_records(table):
    stored(table, "gone@example.org")
    service, src, job, jobs = reconciliation(table, [])
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert table.scan()["Count"] == 0 and job["deleted"] == 1


def test_filter_change_does_not_delete_a_submission_still_in_form(table):
    stored(table, "pending@example.org")
    service, src, job, jobs = reconciliation(table, [submission(1, email="pending@example.org", status="pending")])
    assert src.rows() == []
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert table.scan()["Count"] == 1 and job["deleted"] == 0


@pytest.mark.parametrize("pages", [
    [([], 1)],
    [([], None)],
    [([submission(1)], 2)],
    [([submission(1), submission(1)], 2)],
    [([submission(n) for n in range(100)], 101), ([], 101)],
    [([submission(n) for n in range(100)], 101), ([submission(100)], 102)],
])
def test_incomplete_duplicate_or_changing_source_never_deletes(table, pages):
    stored(table, "keep@example.org")
    service, src, job, jobs = reconciliation(table, [])
    src.client.page.side_effect = pages
    with pytest.raises(AppError):
        service.reconcile(src, job, jobs, lambda: 900000)
    assert table.scan()["Count"] == 1 and job["deleted"] == 0


def test_source_error_or_invalid_email_never_deletes(table):
    stored(table, "keep@example.org")
    service, src, job, jobs = reconciliation(table, [submission(1, email="bad-email")])
    with pytest.raises(AppError):
        service.reconcile(src, job, jobs, lambda: 900000)
    src.client.page.side_effect = AppError("Source unavailable")
    with pytest.raises(AppError):
        service.reconcile(src, job, jobs, lambda: 900000)
    assert table.scan()["Count"] == 1


def test_time_limit_checkpoints_deletions_and_retries(table):
    stored(table, "one@example.org")
    stored(table, "two@example.org")
    service, src, job, jobs = reconciliation(table, [])
    assert not service.reconcile(src, job, jobs, Mock(side_effect=[20000, 10000]))
    assert job["deleted"] == 1 and table.scan()["Count"] == 1
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert job["deleted"] == 2 and table.scan()["Count"] == 0


def test_concurrently_updated_member_is_not_deleted(table):
    stored(table, "keep@example.org")
    service, src, job, jobs = reconciliation(table, [])
    original_delete = table.delete_item
    def update_before_delete(**kwargs):
        table.update_item(Key=kwargs["Key"], UpdateExpression="SET LastSyncedAt = :now", ExpressionAttributeValues={":now": "2026-02-01"})
        return original_delete(**kwargs)
    table.delete_item = Mock(side_effect=update_before_delete)
    assert service.reconcile(src, job, jobs, lambda: 900000)
    assert table.scan()["Count"] == 1 and job["deleted"] == 0


def test_finalization_runs_only_after_upserts_and_retries_its_own_phase():
    jobs = MemoryJobRepository("members")
    job = jobs.start()
    src = source([submission(n) for n in range(9)])
    service = Mock()
    service.upsert.return_value = "created"
    dispatch = Mock()
    finalize = Mock(side_effect=[False, True])
    runner = SyncRunner(jobs, service, src, src, dispatch, finalize=finalize)
    runner.batch(job["jobId"], 0)
    finalize.assert_not_called()
    runner.batch(job["jobId"], 1)
    assert service.upsert.call_count == 9
    assert jobs.latest()["phase"] == "reconcile" and jobs.latest()["status"] == "QUEUED"
    runner.batch(job["jobId"], 2)
    assert jobs.latest()["status"] == "COMPLETED" and service.upsert.call_count == 9


def test_source_failure_does_not_run_finalization():
    jobs = MemoryJobRepository("members")
    job = jobs.start()
    src = Mock()
    src.page.side_effect = AppError("Source unavailable")
    finalize = Mock()
    SyncRunner(jobs, Mock(), Mock(), src, Mock(), finalize=finalize).batch(job["jobId"], 0)
    assert jobs.latest()["status"] == "FAILED"
    finalize.assert_not_called()
