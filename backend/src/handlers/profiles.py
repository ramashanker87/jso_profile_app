from typing import Any
from src.errors import AppError


def handle(runtime: Any, query: dict[str, str]) -> dict[str, Any]:
    try:
        page, size = int(query.get("page", "1")), int(query.get("pageSize", "25"))
    except ValueError:
        raise AppError("Page and pageSize must be integers.") from None
    return runtime.profile_service().list(
        query.get("search", ""), query.get("theme", ""), page, size
    )
