from typing import Any
from uuid import UUID
from src.errors import AppError
from src.models.profile import public_profile
from src.repositories.profile_repository import ProfileRepository
from src.services.storage_service import StorageService


class ProfileService:
    def __init__(self, repository: ProfileRepository, storage: StorageService, members_only: bool = False):
        self.repository, self.storage = repository, storage
        self.members_only = members_only

    def list(
        self, search: str = "", theme: str = "", page: int = 1, page_size: int = 25
    ) -> dict[str, Any]:
        if (
            page < 1
            or not 1 <= page_size <= 100
            or len(search) > 200
            or len(theme) > 300
        ):
            raise AppError("Invalid search or pagination parameters.")
        profiles = [p for p in self.repository.all()
                    if p.get("active", True) and not p.get("mergedInto")
                    and (not self.members_only or p.get("source") == "google_sheets")]
        themes = sorted({p.get("theme", "Other") for p in profiles})
        query = search.casefold().strip()
        filtered = [
            p
            for p in profiles
            if (not theme or p.get("theme", "").casefold() == theme.casefold())
            and (
                not query
                or query
                in " ".join(
                    str(p.get(k, ""))
                    for k in ("name", "email", "linkedinUrl", "theme", "supportRaw", "member")
                ).casefold()
            )
        ]
        filtered.sort(
            key=lambda p: (p.get("submissionDate", ""), p["profileId"]), reverse=True
        )
        start = (page - 1) * page_size
        return {
            "items": [public_profile(p) for p in filtered[start : start + page_size]],
            "page": page,
            "pageSize": page_size,
            "total": len(filtered),
            "totalProfiles": len(profiles),
            "themes": themes,
            "lastSyncedAt": max(
                (p.get("lastSyncedAt", "") for p in profiles), default=None
            ),
        }

    def get(self, profile_id: str) -> dict[str, Any]:
        try:
            UUID(profile_id)
        except (ValueError, AttributeError):
            raise AppError("Invalid profile ID.") from None
        profile = self.repository.get(profile_id)
        if (not profile or not profile.get("active", True) or profile.get("mergedInto")
                or self.members_only and profile.get("source") != "google_sheets"):
            raise AppError("Profile not found.", 404, "NOT_FOUND")
        return profile

    def document(self, profile_id: str, download: bool = False) -> dict[str, Any]:
        item = self.get(profile_id)
        if not item.get("pdf"):
            raise AppError("PDF is not available.", 404, "NO_DOCUMENT")
        return self.storage.signed_url(item["pdf"], download)
