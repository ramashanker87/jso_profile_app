"""Read the standalone member table through the authenticated application API."""
from src.errors import AppError
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from collections import Counter
import json
import re
from pathlib import Path

COUNTRY_NAMES = json.loads((Path(__file__).resolve().parents[1] / "data/country-names.json").read_text())

EDITABLE_FIELDS = ("Full Name", "Phone", "Chapter", "Country", "Region", "City/Place", "Address",
                   "Educational Background", "Professional Experience", "Areas of Interest",
                   "Skills/Expertise", "Motivation", "Support Type", "Comments")

REGIONS = ("North America", "South America", "Europe", "Africa", "Asia", "Middle East", "Oceania")

def effective_member(item):
    return {**item, **{k: v for k, v in item.get("SelfEdits", {}).items() if k in EDITABLE_FIELDS}}

from src.services.sheets_service import SheetMapper
from src.models.profile import public_profile


COUNTRY_ALIASES = {
    "us": "United States", "usa": "United States", "u.s.a.": "United States",
    "united states of america": "United States",
    "united kungdom": "United Kingdom",
    "uk": "United Kingdom", "u.k.": "United Kingdom", "england": "United Kingdom",
    "uae": "United Arab Emirates", "dubai": "United Arab Emirates",
    "malta, europe.": "Malta",
}


def member_countries(value):
    value = " ".join(str(value or "").split())
    if not value:
        return ["Not specified"]
    if value.casefold() == "not specified":
        return ["Not specified"]
    if value.casefold() == "uae and oman":
        return ["United Arab Emirates", "Oman"]
    return [COUNTRY_ALIASES.get(value.casefold(), COUNTRY_NAMES.get(value.casefold(), value.title()))]


def location_countries(item):
    countries = member_countries(item.get("Country"))
    known = set(COUNTRY_NAMES.values())
    if all(c in known for c in countries):
        return countries
    # An explicit country at the end of an address can fill a missing/unrecognized
    # country. Never guess coordinates from streets, postcodes or city names.
    address = " ".join(str(item.get("Address", "")).split()).casefold().rstrip(" .")
    aliases = {**COUNTRY_NAMES, **COUNTRY_ALIASES}
    for alias in sorted(aliases, key=len, reverse=True):
        if len(alias) < 3:
            continue
        if re.search(r"(?:^|[\s,;])" + re.escape(alias) + r"$", address):
            return [aliases[alias]]
    return countries


class MemberService:
    def __init__(self, table, storage=None):
        self.table, self.storage = table, storage

    def public(self, item):
        item = effective_member(item)
        source = SheetMapper().parse(item)
        result = public_profile({
            "profileId": source.email, "name": source.name, "email": source.email,
            "member": source.member, "supportRaw": source.support_raw,
            "theme": source.theme, "submissionDate": source.submission_date,
            "source": "Member directory", "syncStatus": "PARTIAL" if item.get("MemberSyncError") else "SUCCESS",
            "syncError": item.get("MemberSyncError"), "lastSyncedAt": item.get("LastSyncedAt"),
        })
        result["photoUrl"] = self.storage.photo_url(item["Photo"]) if self.storage and item.get("Photo") else None
        return result

    def list(self, search="", page=1, page_size=25, country="", chapter="", region=""):
        if page < 1 or not 1 <= page_size <= 100 or len(search) > 200 or any(len(value) > 4000 for value in (country, chapter, region)):
            raise AppError("Invalid member search or pagination parameters.")
        items = []
        arguments = {"ConsistentRead": True}
        while True:
            response = self.table.scan(**arguments)
            items.extend(effective_member(item) for item in response.get("Items", [])
                         if item.get("Status", "").strip().casefold() == "active")
            if not response.get("LastEvaluatedKey"):
                break
            arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        countries = sorted({country_name for item in items
                            for country_name in location_countries(item)})
        selected = set(member_countries(country)) if country.strip() else set()
        query = search.strip().casefold()
        searched = [item for item in items
                    if not query or query in " ".join(
                        str(item.get(key, "")) for key in ("Full Name", "Email", "Membership ID", "Unique ID",
                            "Chapter", "Country", "Region", "City/Place", "Address", "Areas of Interest", "Skills/Expertise")
                    ).casefold()]
        searched = [item for item in searched
                    if (not chapter or item.get("Chapter", "").strip().casefold() == chapter.strip().casefold())
                    and (not region or item.get("Region", "").strip().casefold() == region.strip().casefold())]
        counts = Counter(country_name for item in searched for country_name in set(location_countries(item)))
        filtered = [item for item in searched
                    if not selected or selected.intersection(location_countries(item))]
        filtered.sort(key=lambda item: (item.get("Full Name", "").casefold(), item["Email"]))
        start = (page - 1) * page_size
        return {"items": [self.public(item) for item in filtered[start:start + page_size]],
                "page": page, "pageSize": page_size, "total": len(filtered),
                "totalProfiles": len(items), "countries": countries,
                "chapters": sorted({item.get("Chapter", "").strip() for item in items} - {""}),
                "regions": list(REGIONS),
                "countryCounts": [{"country": name, "count": count} for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))],
                "mapTotal": len(searched), "themes": [], "lastSyncedAt": max((item.get("LastSyncedAt", "") for item in items), default="") or None}

    def get(self, email):
        email = email.strip().casefold()
        if not email or len(email) > 320:
            raise AppError("Invalid member email.")
        item = self.table.get_item(Key={"Email": email}, ConsistentRead=True).get("Item")
        if not item or item.get("Status", "").strip().casefold() != "active":
            raise AppError("Member not found.", 404, "NOT_FOUND")
        return self.public(item)

    def update(self, email, fields, subject):
        if not isinstance(fields, dict) or not fields or set(fields) - set(EDITABLE_FIELDS):
            raise AppError("Only personal information fields can be edited.")
        if any(not isinstance(v, str) or len(v) > 4000 for v in fields.values()):
            raise AppError("Each field must be text with at most 4000 characters.")
        fields = {k: v.strip() for k, v in fields.items()}
        if "Full Name" in fields and not fields["Full Name"]:
            raise AppError("Full name is required.")
        if fields.get("Region") and fields["Region"] not in REGIONS:
            raise AppError("Select a valid region.")
        # Store a complete personal override separately from source-managed fields.
        current = self.table.get_item(Key={"Email": email}, ConsistentRead=True).get("Item")
        if not current or current.get("Status", "").strip().casefold() != "active":
            raise AppError("Member not found.", 404, "NOT_FOUND")
        edits = {**current.get("SelfEdits", {}), **fields}
        effective = {**current, **edits}
        countries = member_countries(effective.get("Country"))
        middle_east = {"Iraq", "Iran", "Saudi Arabia", "Kuwait", "Oman", "Bahrain", "Lebanon",
                       "Yemen", "Syria", "Jordan", "Qatar", "United Arab Emirates"}
        region = effective.get("Region", "")
        if region == "Asia" and ("India" in countries or middle_east.intersection(countries)):
            raise AppError("Asia excludes India and countries in the Middle East region.")
        if region == "Middle East" and not set(countries).issubset(middle_east):
            raise AppError("The Middle East region requires one of its twelve listed countries.")
        try:
            result = self.table.update_item(
                Key={"Email": email},
                UpdateExpression="SET SelfEdits = :edits, SelfEditedAt = :time, SelfEditedBy = :sub",
                ConditionExpression="attribute_exists(Email) AND #status = :status",
                ExpressionAttributeNames={"#status": "Status"},
                ExpressionAttributeValues={":edits": edits, ":time": datetime.now(timezone.utc).isoformat(),
                                           ":sub": subject, ":status": current["Status"]},
                ReturnValues="ALL_NEW")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AppError("Member changed; reload and try again.", 409, "CONFLICT") from None
            raise
        return self.public(result["Attributes"])
