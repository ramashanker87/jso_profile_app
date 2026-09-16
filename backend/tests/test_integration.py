import base64
from dataclasses import replace
import hashlib
import hmac
import json
from unittest.mock import Mock
import pytest
from src.errors import AppError, DocumentError
from src.handlers.api import handle
from src.handlers.worker import handle as worker
from src.models.profile import profile_id
from src.services.neetform_parser import NeetoSubmissionMapper
from src.services.sync_service import SyncRunner
from src.security.webhook_security import verify_signature
from conftest import event


def signed(raw):
    return "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()


def test_raw_signature_bytes_and_invalid():
    body = b'{ "name": "A & B", "unicode": "\\u00e9" }'
    assert verify_signature(body, signed(body), "test-secret")
    assert not verify_signature(
        json.dumps(json.loads(body)).encode(), signed(body), "test-secret"
    )
    assert not verify_signature(body, "sha256=" + "0" * 64, "test-secret")
    assert not verify_signature(body, "", "test-secret")


def test_webhook_valid_base64_and_duplicate(runtime, payload):
    raw = json.dumps(payload).encode()
    request = event(
        "/webhooks/neetform",
        "POST",
        base64.b64encode(raw).decode(),
        {"X-Neeto-Webhook-Signature": signed(raw)},
        False,
    )
    request["isBase64Encoded"] = True
    assert handle(request, runtime)["statusCode"] == 202
    message = runtime.dispatch.call_args.args[0]
    worker(message, None, runtime)
    worker(message, None, runtime)
    assert len(runtime.profiles.all()) == 1
    assert runtime.storage.upload.call_count == 1


def test_invalid_signature_before_json(runtime):
    request = event(
        "/webhooks/neetform",
        "POST",
        "not json",
        {"x-neeto-webhook-signature": "invalid"},
        False,
    )
    assert handle(request, runtime)["statusCode"] == 403
    runtime.dispatch.assert_not_called()


def test_valid_signature_invalid_payload(runtime):
    raw = b"not json"
    request = event(
        "/webhooks/neetform",
        "POST",
        raw.decode(),
        {"x-neeto-webhook-signature": signed(raw)},
        False,
    )
    assert handle(request, runtime)["statusCode"] == 400


def test_known_neeto_answers_shape():
    mapper = NeetoSubmissionMapper({"name": "full_name", "file": "upload_1"})
    value = mapper.parse(
        {
            "webhook": {
                "id": "real-shape",
                "submitted_at": "2026-09-07T18:00:00Z",
                "answers": {
                    "full_name": {
                        "field": "Full name",
                        "value": "Amit Kumar",
                        "type": "full_name",
                    },
                    "email": {"field": "Email", "value": "amit@example.com"},
                    "upload_1": {
                        "field": "File upload",
                        "value": [
                            {
                                "filename": "a.pdf",
                                "download_url": "https://files.example/a.pdf",
                            }
                        ],
                    },
                },
            }
        }
    )
    assert value.name == "Amit Kumar" and value.email == "amit@example.com"
    assert value.files[0].name == "a.pdf"


def test_mapping_and_nested_json_files(payload):
    payload["submission"]["responses"] += [
        {"slug": "custom_support", "value": ["time", "money"]},
        {
            "label": "Resume X",
            "value": '{"url":"https://files.example/a.pdf","name":"a.pdf"}',
        },
    ]
    value = NeetoSubmissionMapper(
        {"support": "custom_support", "file": "Resume X"}
    ).parse(payload)
    assert value.support_raw == "time, money"
    assert value.files[0].url == "https://files.example/a.pdf"


def test_profile_create_update_and_public_metadata(runtime, payload):
    source = runtime.mapper().parse(payload)
    assert runtime.sync_service().upsert(source) == "created"
    assert runtime.sync_service().upsert(source) == "unchanged"
    changed = replace(source, theme="Technology")
    runtime.storage.existing.return_value = runtime.storage.upload.return_value
    assert runtime.sync_service().upsert(changed) == "updated"
    assert len(runtime.profiles.all()) == 1
    response = handle(event(), runtime)
    body = json.loads(response["body"])
    assert body["items"][0]["theme"] == "Technology"
    assert "s3Key" not in response["body"] and "http://127" not in response["body"]
    pid = body["items"][0]["profileId"]
    assert handle(event("/profiles/" + pid), runtime)["statusCode"] == 200
    assert handle(event("/profiles/" + pid + "/document"), runtime)["statusCode"] == 200


@pytest.mark.parametrize(
    "code,status",
    [
        ("DOWNLOAD_FAILED", "PARTIAL"),
        ("FILE_TOO_LARGE", "FAILED"),
        ("INVALID_DOCUMENT", "FAILED"),
    ],
)
def test_download_failure_preserves_metadata(runtime, payload, code, status):
    runtime.storage.upload.side_effect = DocumentError("Safe document error", code=code)
    source = runtime.mapper().parse(payload)
    assert runtime.sync_service().upsert(source) == "failed"
    stored = runtime.profiles.get(profile_id("sample-form", source.submission_id))
    assert stored["name"] == "Amit Kumar" and stored["syncStatus"] == status


def test_missing_pdf_and_preserve_previous_document(runtime, payload):
    source = runtime.mapper().parse(payload)
    runtime.sync_service().upsert(source)
    runtime.sync_service().upsert(replace(source, files=[]))
    stored = runtime.profiles.all()[0]
    assert stored["pdf"] and stored["syncStatus"] == "PARTIAL"


def test_missing_pdf_without_previous(runtime, payload):
    runtime.sync_service().upsert(replace(runtime.mapper().parse(payload), files=[]))
    pid = runtime.profiles.all()[0]["profileId"]
    assert handle(event("/profiles/" + pid + "/document"), runtime)["statusCode"] == 404


def test_stale_update_is_ignored(runtime, payload):
    source = replace(
        runtime.mapper().parse(payload), source_updated_at="2026-09-07T20:00:00Z"
    )
    runtime.sync_service().upsert(source)
    assert (
        runtime.sync_service().upsert(
            replace(source, name="Old Name", source_updated_at="2026-09-06T00:00:00Z")
        )
        == "unchanged"
    )
    assert runtime.profiles.all()[0]["name"] == "Amit Kumar"


def test_authorization_assumptions(runtime):
    assert handle(event(authenticated=False), runtime)["statusCode"] == 401
    for path, method in [
        ("/profiles", "GET"),
        ("/profiles/123", "GET"),
        ("/profiles/123/document", "GET"),
        ("/sync", "POST"),
        ("/sync", "GET"),
    ]:
        assert (
            handle(event(path, method, authenticated=False), runtime)["statusCode"]
            == 401
        )
    req = event()
    req["requestContext"]["authorizer"]["jwt"]["claims"]["token_use"] = "id"
    assert handle(req, runtime)["statusCode"] == 401
    req = event()
    req["requestContext"]["authorizer"]["jwt"]["claims"]["client_id"] = "wrong"
    assert handle(req, runtime)["statusCode"] == 403


def test_search_theme_pagination_and_validation(runtime, payload):
    source = runtime.mapper().parse(payload)
    for i, theme in enumerate(["Education", "Health", "Education"]):
        runtime.sync_service().upsert(
            replace(source, submission_id=str(i), name="Amit " + str(i), theme=theme)
        )
    result = runtime.profile_service().list("AMIT", "Education", 2, 1)
    assert (
        result["total"] == 2
        and len(result["items"]) == 1
        and result["themes"] == ["Education", "Health"]
    )
    request = event()
    request["queryStringParameters"] = {"page": "oops"}
    assert handle(request, runtime)["statusCode"] == 400


def test_no_sensitive_exception_output(runtime):
    runtime.profiles.all = Mock(side_effect=RuntimeError("secret-api-key"))
    response = handle(event(), runtime)
    assert response["statusCode"] == 500 and "secret-api-key" not in response["body"]


def test_sync_checkpoints_and_duplicate_jobs(runtime, payload):
    source = payload["submission"]
    rows = [{**source, "id": str(i)} for i in range(23)]
    neeto = Mock()
    neeto.page.side_effect = lambda page, size: (
        rows[(page - 1) * size : page * size],
        len(rows),
    )
    job = runtime.jobs.start()
    messages = [{"action": "sync", "jobId": job["jobId"], "generation": 0}]
    runner = SyncRunner(
        runtime.jobs, runtime.sync_service(), runtime.mapper(), neeto, messages.append
    )
    while messages:
        message = messages.pop(0)
        runner.batch(message["jobId"], message["generation"])
    finished = runtime.jobs.get(job["jobId"])
    assert (
        finished["status"] == "COMPLETED"
        and finished["processed"] == 23
        and finished["created"] == 23
    )
    runner.batch(job["jobId"], 0)
    assert len(runtime.profiles.all()) == 23
    assert runtime.jobs.get(job["jobId"])["processed"] == 23


def test_source_missing_never_deleted(runtime, payload):
    runtime.sync_service().upsert(runtime.mapper().parse(payload))
    neeto = Mock()
    neeto.page.return_value = ([], 0)
    job = runtime.jobs.start()
    SyncRunner(
        runtime.jobs, runtime.sync_service(), runtime.mapper(), neeto, Mock()
    ).batch(job["jobId"], 0)
    assert len(runtime.profiles.all()) == 1


def test_sync_dispatch_failure_records_failed_job(runtime):
    runtime.neeto = Mock()
    runtime.dispatch.side_effect = RuntimeError("private")
    assert handle(event("/sync", "POST"), runtime)["statusCode"] == 503
    assert runtime.jobs.latest()["status"] == "FAILED"


def test_gateway_flattened_groups_use_original_verified_array(runtime):
    from dataclasses import replace
    import base64

    runtime.settings = replace(runtime.settings, required_group="profile-library-users")
    req = event()
    claims = req["requestContext"]["authorizer"]["jwt"]["claims"]
    claims["cognito:groups"] = "[another-group profile-library-users]"
    original = {**claims, "cognito:groups": ["another-group", "profile-library-users"]}

    def header(payload):
        encoded = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        )
        return {
            "authorization": "Bearer header." + encoded + ".gateway-verified-signature"
        }

    req["headers"] = header(original)
    assert handle(req, runtime)["statusCode"] == 200
    # An unrelated group whose name contains spaces cannot grant membership.
    req["headers"] = header(
        {**original, "cognito:groups": ["another-group profile-library-users"]}
    )
    assert handle(req, runtime)["statusCode"] == 403
    req["headers"] = header({**original, "sub": "different-user"})
    assert handle(req, runtime)["statusCode"] == 403


def test_new_source_revision_refreshes_stable_document_url(runtime, payload):
    source = runtime.mapper().parse(payload)
    runtime.sync_service().upsert(source)
    runtime.sync_service().upsert(source)
    assert runtime.storage.upload.call_count == 1
    changed = replace(source, source_updated_at="2026-09-08T18:00:00Z")
    assert runtime.sync_service().upsert(changed) == "updated"
    assert runtime.storage.upload.call_count == 2


def test_slow_page_does_not_create_an_infinite_sync_chain(runtime, payload):
    client = Mock()
    client.page.return_value = ([payload["submission"]], 1)
    job = runtime.jobs.start()
    dispatch = Mock()
    SyncRunner(
        runtime.jobs, runtime.sync_service(), runtime.mapper(), client, dispatch
    ).batch(job["jobId"], 0, lambda: 90000)
    assert runtime.jobs.get(job["jobId"])["status"] == "FAILED"
    dispatch.assert_not_called()


def test_submitted_total_includes_profiles_outside_search_and_page(runtime, payload):
    source = runtime.mapper().parse(payload)
    runtime.sync_service().upsert(source)
    runtime.sync_service().upsert(replace(source, submission_id="second-submission"))
    result = runtime.profile_service().list(search="no-such-profile", page_size=1)
    assert result["totalProfiles"] == 2
    assert result["total"] == 0 and result["items"] == []
    result = runtime.profile_service().list(page_size=1)
    assert result["totalProfiles"] == 2 and len(result["items"]) == 1


@pytest.mark.parametrize(
    "data, expected",
    [({"value": "Education"}, "Education"), ({"value": ""}, "Other"), (None, "Other")],
)
def test_custom_theme_column(payload, data, expected):
    payload["submission"]["field_values"] = [
        {"id": "answer-id", "field_id": "theme-column-id", "data": data},
        {
            "id": "other-answer",
            "field_id": "unrelated-column",
            "data": {"value": "Ignore"},
        },
    ]
    source = NeetoSubmissionMapper({"theme": "theme-column-id"}).parse(payload)
    assert source.theme == expected


def test_missing_custom_theme_column(payload):
    payload["submission"]["responses"] = []
    source = NeetoSubmissionMapper({"theme": "theme-column-id"}).parse(payload)
    assert source.theme == "Other"
