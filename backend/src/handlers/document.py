from typing import Any
from src.errors import AppError


def handle(runtime: Any, profile_id: str, query: dict[str, str]) -> dict[str, Any]:
    disposition = query.get("disposition", "inline")
    if disposition not in ("inline", "attachment"):
        raise AppError("Invalid document disposition.")
    return runtime.profile_service().document(profile_id, disposition == "attachment")
