"""Status-filtered Neeto member imports into the separate email-keyed table."""
from contextlib import nullcontext
import hashlib
import io
import json
import re
from PIL import Image, ImageOps
from botocore.exceptions import ClientError
from src.errors import AppError
from src.models.profile import FileInput, now_iso, profile_id
from src.services.storage_service import SafeDownloader, fingerprint

RESPONSE_COLUMNS = {
    "full-name": "Full Name", "email-address": "Email", "phone-number": "Phone",
    "type-a-question-2": "Country", "type-a-question-8": "City/Place",
    "address-2": "Address", "type-a-question-3": "Educational Background",
    "type-a-question-4": "Professional Experience", "type-a-question-5": "Areas of Interest",
    "type-a-question-6": "Skills/Expertise", "type-a-question-7": "Motivation",
    "unique-id": "Unique ID",
}
CUSTOM_COLUMNS = {
    "6c141a54-49b7-4296-a481-07dc1f9f093a": "Membership ID",
    "1f438883-1112-4b15-a6cb-d8a93ddbfc89": "Comments",
}


def text(value):
    if isinstance(value, dict):
        if "value" in value:
            return text(value["value"])
        if "address" in value:
            return ", ".join(text(part.get("content")) for part in value["address"] if part.get("content"))
        raise AppError("Unexpected member field format.", 502, "MEMBER_MAPPING")
    if isinstance(value, list):
        return ", ".join(text(v) for v in value if v is not None)
    return str(value).strip() if value is not None else ""


class MemberSource:
    """Read all pages before writes; filter explicitly because Neeto ignores URL filters."""
    def __init__(self, client, form_id, status_field, status_value):
        if not form_id or bool(status_field) != bool(status_value):
            raise AppError("Configure the member form and either both status filter settings or neither.", 503, "NOT_CONFIGURED")
        self.client, self.form_id = client, form_id
        self.status_field, self.status_value = status_field, status_value
        self._rows = None

    def rows(self):
        if self._rows is not None:
            return self._rows
        selected = []
        expected_total = None
        submission_ids = set()
        for page in range(1, 101):
            entries, total = self.client.page(page, 100)
            # A short, duplicate or shifting listing must never look like deletions.
            if not isinstance(total, int) or total < 0:
                raise AppError("Member source did not provide a valid total; sync stopped.", 502, "INCOMPLETE_SOURCE")
            if expected_total is None:
                expected_total = total
            if total != expected_total or (not entries and len(submission_ids) != total):
                raise AppError("Member source changed or returned an incomplete page. Retry sync.", 502, "INCOMPLETE_SOURCE")
            for item in entries:
                sid = item.get("id")
                if not sid or sid in submission_ids:
                    raise AppError("Member source contains missing or duplicate submission IDs. Retry sync.", 502, "INCOMPLETE_SOURCE")
                submission_ids.add(sid)
                fields = {v.get("field_id"): v.get("data", {}) for v in item.get("field_values", [])}
                values = fields.get(self.status_field, {}).get("values", [])
                if self.status_value and (not isinstance(values, list) or self.status_value not in values):
                    continue
                responses = {v.get("slug"): v.get("value") for v in item.get("responses", [])}
                row = {column: text(responses[slug]) for slug, column in RESPONSE_COLUMNS.items() if slug in responses}
                for fid, column in CUSTOM_COLUMNS.items():
                    if fid in fields:
                        row[column] = text(fields[fid].get("value"))
                email = row.get("Email", "").casefold()
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise AppError("A selected member has a missing or invalid email. Correct the source before syncing.", 422, "MEMBER_EMAIL")
                if not item.get("id") or not item.get("created_at"):
                    raise AppError("A selected member is missing its submission ID or date.", 502, "MEMBER_MAPPING")
                row.update(Email=email, Status="Active")
                row["Full Name"] = row.get("Full Name") or email
                upload = responses.get("file-upload") or {}
                files = upload.get("files", []) if isinstance(upload, dict) else []
                photo = next((f for f in files if isinstance(f, dict) and f.get("url")), None)
                selected.append({"row": row, "submissionId": str(item["id"]), "date": str(item["created_at"]), "photo": photo})
            if len(submission_ids) == expected_total:
                break
            if len(submission_ids) > expected_total or len(entries) < 100:
                raise AppError("Member source returned an incomplete listing. Retry sync.", 502, "INCOMPLETE_SOURCE")
        else:
            raise AppError("Member source exceeds the supported pagination limit.", 502, "PAGINATION_LIMIT")
        # Newer selected submissions supply updated values; older nonblank fields survive.
        merged = {}
        for item in sorted(selected, key=lambda i: (i["date"], i["submissionId"])):
            email = item["row"]["Email"]
            previous = merged.get(email)
            if previous:
                row = {**previous["row"], **{k: v for k, v in item["row"].items() if v}}
                ids = previous["submissionIds"] + [item["submissionId"]]
                photo = item["photo"] or previous["photo"]
            else:
                row, ids, photo = item["row"], [item["submissionId"]], item["photo"]
                row["Submitted On (Earliest)"] = item["date"]
            row["Number of Submissions"] = str(len(ids))
            merged[email] = {"row": row, "submissionIds": ids, "photo": photo, "formId": self.form_id}
        self._rows = [merged[email] for email in sorted(merged)]
        return self._rows

    def page(self, number, size):
        rows = self.rows()
        return rows[(number - 1) * size:number * size], len(rows)

    def parse(self, row):
        return row


class MemberSyncService:
    def __init__(self, table, storage, settings, locks=None):
        self.table, self.storage, self.settings, self.locks = table, storage, settings, locks

    def upsert(self, source):
        email = source["row"]["Email"]
        scope = "member:" + profile_id(source["formId"], email)
        with self.locks.hold(scope) if self.locks else nullcontext():
            return self._upsert(source)

    def _upsert(self, source):
        row = dict(source["row"])
        email = row["Email"]
        previous = self.table.get_item(Key={"Email": email}, ConsistentRead=True).get("Item", {})
        photo = source["photo"]
        photo_fingerprint = fingerprint(FileInput(photo["url"], photo.get("name", ""))) if photo else ""
        digest = hashlib.sha256(json.dumps({"row": row, "ids": source["submissionIds"], "photo": photo_fingerprint}, sort_keys=True).encode()).hexdigest()
        unchanged = previous.get("NeetoFingerprint") == digest
        row = {k: v for k, v in row.items() if v and k != "Email"}
        # Preserve fields and photos owned by earlier imports, rather than replacing items.
        sources = previous.get("Sources", "")
        label = "NeetoForm " + source["formId"]
        row["Sources"] = sources if label in sources else "; ".join(v for v in [sources, label] if v)
        row.update(NeetoFormId=source["formId"], NeetoSubmissionIds=source["submissionIds"],
                   NeetoFingerprint=digest, LastSyncedAt=now_iso(), MemberSyncError="")
        if photo and (previous.get("NeetoPhotoFingerprint") != photo_fingerprint or not previous.get("Photo")):
            try:
                downloader = SafeDownloader(self.settings.attachment_hosts, self.settings.max_file_bytes, self.settings.local, image=True)
                with downloader.download(photo["url"]) as (stream, _):
                    with Image.open(stream) as original:
                        if original.width * original.height > 25000000:
                            raise ValueError("Image dimensions too large")
                        picture = ImageOps.exif_transpose(original).convert("RGB")
                        picture.thumbnail((800, 800))
                        data = io.BytesIO()
                        picture.save(data, format="JPEG", quality=88)
                row["Photo"] = self.storage.upload_photo(profile_id("member-photo", email), data.getvalue())
                row["NeetoPhotoFingerprint"] = photo_fingerprint
            except Exception:
                row["MemberSyncError"] = "Member details saved; photo could not be imported. Retry sync."
        names = {f"#k{n}": k for n, k in enumerate(row)}
        values = {f":v{n}": v for n, v in enumerate(row.values())}
        self.table.update_item(Key={"Email": email},
            UpdateExpression="SET " + ", ".join(f"#k{n} = :v{n}" for n in range(len(row))),
            ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        return "failed" if row["MemberSyncError"] else "unchanged" if unchanged else "updated" if previous else "created"

    def reconcile(self, source, job, jobs, remaining_ms):
        # Always inspect the full form, even if a future import uses a status filter.
        # Re-read at completion rather than deleting from a stale import page.
        fresh = MemberSource(source.client, source.form_id, "", "")
        emails = {item["row"]["Email"] for item in fresh.rows()}
        candidates = []
        arguments = {"ConsistentRead": True, "ProjectionExpression": "Email, NeetoFormId, NeetoFingerprint, LastSyncedAt"}
        while True:
            response = self.table.scan(**arguments)
            candidates.extend(item for item in response.get("Items", [])
                              if item.get("NeetoFormId") == source.form_id and item["Email"] not in emails)
            if not response.get("LastEvaluatedKey"):
                break
            arguments["ExclusiveStartKey"] = response["LastEvaluatedKey"]
        for item in candidates:
            if remaining_ms() < 15000:
                return False
            names = {"#form": "NeetoFormId", "#email": "Email"}
            values = {":form": source.form_id}
            conditions = ["attribute_exists(#email)", "#form = :form"]
            for n, key in enumerate(("NeetoFingerprint", "LastSyncedAt")):
                names[f"#v{n}"] = key
                if key in item:
                    conditions.append(f"#v{n} = :v{n}")
                    values[f":v{n}"] = item[key]
                else:
                    conditions.append(f"attribute_not_exists(#v{n})")
            try:
                self.table.delete_item(Key={"Email": item["Email"]},
                    ConditionExpression=" AND ".join(conditions),
                    ExpressionAttributeNames=names, ExpressionAttributeValues=values)
            except ClientError as error:
                if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    continue  # A concurrent update or deletion won; do not overwrite it.
                raise
            job["deleted"] = int(job.get("deleted", 0)) + 1
            jobs.save(job)
        return True
