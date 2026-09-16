"""Read-only member directory integration with Google Sheets and Drive."""
import io
import json
import os
import re
from urllib.parse import quote, urlparse, parse_qs

from src.errors import AppError, DocumentError
from src.models.profile import ProfileInput

COLUMNS = {
    "Phone": "phone", "Chapter": "chapter", "Region": "region", "Country": "country", "City/Place": "city",
    "Address": "address", "Membership ID": "membershipId", "Status": "status",
    "Role": "role", "Role Title": "roleTitle",
    "Educational Background": "education", "Professional Experience": "experience",
    "Areas of Interest": "interests", "Skills/Expertise": "skills",
    "Motivation": "motivation", "Support Type": "supportType",
    "File Upload": "fileUpload", "Comments": "comments",
    "Submitted On (Earliest)": "submittedOn", "Number of Submissions": "submissionCount",
    "Sources": "sources", "Unique ID": "sourceUniqueId",
}


class SheetMapper:
    def parse(self, row):
        email = row.get("Email", "").strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise AppError("Member row has a missing or invalid email.")
        details = {key: row.get(column, "").strip() for column, key in COLUMNS.items()}
        details["status"] = details["status"].casefold()
        return ProfileInput(
            submission_id=email, email=email, name=row.get("Full Name", "").strip() or email,
            linkedin_url="", support_raw=details["supportType"],
            theme=details["interests"] or "Other", submission_date=details["submittedOn"],
            source_updated_at="", source="google_sheets", member=details,
        )


class GoogleSheetsClient:
    def __init__(self, settings, secrets):
        self.settings = settings
        try:
            from google.oauth2.service_account import Credentials
            from google.auth.transport.requests import AuthorizedSession
            raw = secrets.get().get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
            scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly",
                      "https://www.googleapis.com/auth/drive.readonly"]
            credentials = (Credentials.from_service_account_info(json.loads(raw), scopes=scopes)
                           if raw else Credentials.from_service_account_file(
                               os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=scopes))
            self.session = AuthorizedSession(credentials)
        except Exception:
            raise AppError("Google service-account credentials are not configured or invalid.",
                           503, "NOT_CONFIGURED") from None

    def get_json(self, url, **params):
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception:
            raise AppError("Cannot read Google data. Check service-account sharing and enabled APIs.",
                           502, "GOOGLE_READ_FAILED") from None

    def rows(self, required_columns=("Email", "Full Name", "Status")):
        base = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(self.settings.google_sheet_id, safe="")
        sheets = self.get_json(base, fields="sheets.properties").get("sheets", [])
        title = next((s["properties"]["title"] for s in sheets
                      if str(s["properties"]["sheetId"]) == self.settings.google_sheet_gid), None)
        if title is None:
            raise AppError("The configured member sheet tab was not found.")
        span = "'" + title.replace("'", "''") + "'!A:AZ"
        values = self.get_json(base + "/values/" + quote(span, safe="")).get("values", [])
        headers = [str(v).strip() for v in values[0]] if values else []
        missing = set(required_columns) - set(headers)
        if missing:
            raise AppError("Member sheet is missing columns: " + ", ".join(sorted(missing)))
        return [dict(zip(headers, map(str, row))) for row in values[1:]
                if any(str(v).strip() for v in row)]

    def page(self, number, size):
        source_rows = self.rows()
        # Collapse duplicate email rows before pagination. An inactive duplicate wins
        # conservatively so conflicting source rows cannot expose an inactive member.
        rows = {}
        for index, row in enumerate(source_rows):
            key = row.get("Email", "").strip().casefold() or f"invalid-row-{index}"
            previous = rows.get(key)
            if previous is None or row.get("Status", "").strip().casefold() != "active":
                rows[key] = row
        entries = list(rows.values())
        return entries[(number - 1) * size:number * size], len(entries)

    def photo(self, value):
        from PIL import Image, ImageOps
        # Credentials are sent only to Google's API, never to sheet-provided URLs.
        urls = re.findall(r"https://[^\s,]+", value)
        for url in urls:
            parsed = urlparse(url)
            if parsed.hostname not in ("drive.google.com", "docs.google.com"):
                continue
            match = re.search(r"/d/([\w-]+)", parsed.path)
            fid = match.group(1) if match else parse_qs(parsed.query).get("id", [""])[0]
            if not re.fullmatch(r"[\w-]+", fid):
                continue
            base = "https://www.googleapis.com/drive/v3/files/" + fid
            metadata = self.get_json(base, fields="mimeType", supportsAllDrives="true")
            if metadata.get("mimeType") not in ("image/jpeg", "image/png", "image/webp"):
                continue
            try:
                with self.session.get(base, params={"alt": "media", "supportsAllDrives": "true"},
                                      stream=True, timeout=30) as response:
                    response.raise_for_status()
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > self.settings.max_file_bytes:
                            raise ValueError("Image too large")
                with Image.open(io.BytesIO(data)) as original:
                    if original.width * original.height > 25000000:
                        raise ValueError("Image dimensions too large")
                    picture = ImageOps.exif_transpose(original).convert("RGB")
                    picture.thumbnail((800, 800))
                    output = io.BytesIO()
                    picture.save(output, format="JPEG", quality=88)
                    return output.getvalue()
            except Exception:
                raise DocumentError("Member photo could not be downloaded or decoded.") from None
        raise DocumentError("No supported Google Drive photo found in File Upload.")
