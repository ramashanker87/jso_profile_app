import hashlib
import hmac
import os
from pathlib import Path
import sys
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()
raw = Path(sys.argv[2]).read_bytes()
secret = os.getenv("NEETO_WEBHOOK_SECRET") or "local-webhook-secret"
invalid = "--invalid" in sys.argv
signature = "sha256=" + (
    "0" * 64 if invalid else hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
)
request = urllib.request.Request(
    sys.argv[1],
    data=raw,
    headers={
        "Content-Type": "application/json",
        "x-neeto-webhook-signature": signature,
    },
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=40) as result:
        status = result.status
except urllib.error.HTTPError as error:
    status = error.code
expected = (401, 403) if invalid else (200, 202)
print("Webhook HTTP status:", status)
if status not in expected:
    raise SystemExit("Unexpected webhook response.")
