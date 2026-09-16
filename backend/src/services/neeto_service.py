import json
from typing import Any, Protocol
from urllib.parse import quote, urlparse
import urllib3
from src.errors import AppError


class NeetoClient(Protocol):
    def page(
        self, number: int, size: int = 20
    ) -> tuple[list[dict[str, Any]], int | None]: ...


class HttpNeetoClient:
    def __init__(self, base_url: str, form_id: str, api_key: str, local: bool = False):
        parsed = urlparse(base_url)
        if (
            (
                parsed.scheme != "https"
                and not (local and parsed.hostname in ("127.0.0.1", "localhost"))
            )
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise AppError("Invalid Neeto API base URL.", 503, "NOT_CONFIGURED")
        if not api_key or not form_id:
            raise AppError(
                "Neeto API key or form ID is not configured.", 503, "NOT_CONFIGURED"
            )
        self.url = (
            base_url.rstrip("/") + "/forms/" + quote(form_id, safe="") + "/submissions"
        )
        self.key = api_key
        self.http = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=5, read=20),
            retries=urllib3.Retry(
                total=2,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                respect_retry_after_header=False,
            ),
        )

    def page(
        self, number: int, size: int = 20
    ) -> tuple[list[dict[str, Any]], int | None]:
        try:
            result = self.http.request(
                "GET",
                self.url,
                fields={"page_number": number, "page_size": size},
                headers={"X-Api-Key": self.key, "Accept": "application/json"},
                redirect=False,
            )
            if result.status != 200:
                raise ValueError()
            payload = json.loads(result.data)
            items = payload["submissions"]
            if not isinstance(items, list):
                raise ValueError()
            return items, (
                int(payload["total_count"])
                if payload.get("total_count") is not None
                else None
            )
        except Exception:
            raise AppError(
                "Unable to retrieve NeetoForm submissions. Check server configuration and retry.",
                502,
                "NEETO_UNAVAILABLE",
            ) from None
