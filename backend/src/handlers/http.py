import base64
from decimal import Decimal
import json
from typing import Any
from src.errors import AppError


def raw_body(event: dict[str, Any]) -> bytes:
    body = event.get("body") or ""
    try:
        raw = (
            base64.b64decode(body, validate=True)
            if event.get("isBase64Encoded")
            else body.encode("utf-8")
        )
    except (ValueError, TypeError, UnicodeError):
        raise AppError("Invalid request body.") from None
    if len(raw) > 200 * 1024:
        raise AppError("Request body exceeds 200 KB.", 413, "PAYLOAD_TOO_LARGE")
    return raw


def response(status: int, data: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
        "body": json.dumps(
            data,
            default=lambda value: (
                int(value) if isinstance(value, Decimal) else str(value)
            ),
        ),
    }
