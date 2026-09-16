"""Integration test: mock Neeto -> local worker -> metadata and real PDF."""

import hashlib
import hmac
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

processes = [
    subprocess.Popen([sys.executable, "backend/mock_neeto.py"]),
    subprocess.Popen([sys.executable, "backend/local.py"]),
]


def call(path, method="GET", body=None, headers=None):
    with urlopen(
        Request(
            "http://127.0.0.1:8000" + path,
            method=method,
            data=body,
            headers=headers or {"Authorization": "Bearer local-dev-token"},
        ),
        timeout=10,
    ) as result:
        return json.load(result)


try:
    for _ in range(50):
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("A test server did not start; check ports 8000/8001.")
        try:
            call("/profiles")
            break
        except URLError:
            time.sleep(0.1)
    job = call("/sync", "POST")
    for _ in range(100):
        job = call("/sync/" + job["jobId"])
        if job["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.1)
    assert job["status"] == "COMPLETED" and job["created"] == 3, job
    profiles = call("/profiles")
    assert profiles["total"] == 3
    document = call("/profiles/" + profiles["items"][0]["profileId"] + "/document")
    with urlopen(document["url"]) as response:
        assert response.read(5) == b"%PDF-"
    raw = Path("backend/tests/fixtures/webhook.json").read_bytes()
    signature = (
        "sha256=" + hmac.new(b"local-webhook-secret", raw, hashlib.sha256).hexdigest()
    )
    for _ in range(2):
        call(
            "/webhooks/neetform", "POST", raw, {"x-neeto-webhook-signature": signature}
        )
    for _ in range(50):
        if call("/profiles")["total"] == 4:
            break
        time.sleep(0.1)
    assert call("/profiles")["total"] == 4
    try:
        call(
            "/webhooks/neetform", "POST", raw, {"x-neeto-webhook-signature": "invalid"}
        )
        raise AssertionError("Invalid signature accepted")
    except HTTPError as error:
        assert error.code == 403
    print(
        "PASS: mock API pagination/import, PDF download, signed webhook, duplicate webhook, invalid signature."
    )
finally:
    for process in processes:
        process.terminate()
    for process in processes:
        process.wait(timeout=5)
