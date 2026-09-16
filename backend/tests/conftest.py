from pathlib import Path
from unittest.mock import Mock
import json
import pytest
from src.config import Settings
from src.runtime import Runtime
from src.repositories.profile_repository import MemoryProfileRepository
from src.repositories.job_repository import MemoryJobRepository


@pytest.fixture
def payload():
    return json.loads((Path(__file__).parent / "fixtures/webhook.json").read_text())


@pytest.fixture
def runtime():
    settings = Settings(
        form_id="sample-form", cognito_client_id="test-client", field_mapping={}
    )
    storage = Mock()
    cached = {}
    document = {
        "fileName": "profile.pdf",
        "s3Key": "profiles/test/current/profile.pdf",
        "contentType": "application/pdf",
        "size": 100,
    }
    storage.existing.side_effect = lambda pid, fp, name: cached.get((pid, fp))

    def upload(pid, file, fp):
        cached[(pid, fp)] = document
        return document

    storage.upload.side_effect = upload
    storage.upload.return_value = document
    storage.signed_url.return_value = {
        "url": "https://private.example/signed",
        "expiresIn": 900,
        "fileName": "profile.pdf",
    }
    secrets = Mock()
    secrets.get.return_value = {
        "NEETO_API_KEY": "test-key",
        "NEETO_WEBHOOK_SECRET": "test-secret",
    }
    return Runtime(
        settings,
        MemoryProfileRepository(),
        MemoryJobRepository(),
        storage,
        secrets,
        Mock(),
    )


def event(path="/profiles", method="GET", body="", headers=None, authenticated=True):
    result = {
        "rawPath": path,
        "body": body,
        "headers": headers or {},
        "requestContext": {"http": {"method": method}},
    }
    if authenticated:
        result["requestContext"]["authorizer"] = {
            "jwt": {
                "claims": {
                    "sub": "test-user",
                    "token_use": "access",
                    "client_id": "test-client",
                }
            }
        }
    return result
