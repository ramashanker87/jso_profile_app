from typing import Any
from src.models.profile import public_profile


def handle(runtime: Any, profile_id: str) -> dict[str, Any]:
    item = runtime.profile_service().get(profile_id)
    result = public_profile(item)
    result["photoUrl"] = runtime.storage.photo_url(item["photo"]) if item.get("photo") else None
    return result
