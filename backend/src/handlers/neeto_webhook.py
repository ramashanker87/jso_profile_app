import json
from typing import Any
from src.errors import AppError
from src.handlers.http import raw_body
from src.security.webhook_security import verify_signature


def handle(runtime: Any, event: dict[str, Any]) -> dict[str, Any]:
    if runtime.settings.google_sheet_id:
        raise AppError("Neeto webhooks are disabled while the member sheet is the sync source.", 409, "SOURCE_DISABLED")
    raw = raw_body(event)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    secret = runtime.secrets.get()["NEETO_WEBHOOK_SECRET"]
    if not secret:
        raise AppError("Webhook integration is not configured.", 503, "NOT_CONFIGURED")
    if not verify_signature(raw, headers.get("x-neeto-webhook-signature", ""), secret):
        raise AppError("Invalid webhook signature.", 403, "INVALID_SIGNATURE")
    # Signature has been checked against original bytes, including base64 decoding.
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        raise AppError("Invalid JSON payload.") from None
    source = runtime.mapper().parse(payload)
    runtime.dispatch({"action": "webhook", "profile": source.to_dict()})
    return {"accepted": True, "submissionId": source.submission_id}
