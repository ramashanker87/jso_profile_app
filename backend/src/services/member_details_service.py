"""Import the requested spreadsheet columns into a separate email-keyed table."""
import re
from src.errors import AppError

MEMBER_COLUMNS = (
    "Full Name", "Email", "Phone", "Chapter", "Country", "Region", "City/Place", "Address",
    "Membership ID", "Status", "Educational Background", "Professional Experience",
    "Areas of Interest", "Skills/Expertise", "Motivation", "Support Type", "Comments",
    "Submitted On (Earliest)", "Number of Submissions", "Sources", "Unique ID",
)


def prepare_members(rows):
    """Validate the complete source before writes; preserve text and leading zeros."""
    members = {}
    inactive = set()
    for number, row in enumerate(rows, 2):
        email = str(row.get("Email", "")).strip().casefold()
        if str(row.get("Status", "")).strip().casefold() != "active":
            inactive.add(email)
            continue
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise AppError(f"Active source row {number} has a missing or invalid email; no rows were written.")
        member = {key: str(row.get(key, "")).strip() for key in MEMBER_COLUMNS}
        member["Email"] = email
        if email in members and member != members[email]:
            raise AppError("Conflicting active rows share an email; resolve duplicate rows before importing.")
        members[email] = member
    return [member for email, member in members.items() if email not in inactive]


def import_members(table, members):
    # put_item replaces only this email's record; retries cannot create duplicates.
    with table.batch_writer(overwrite_by_pkeys=["Email"]) as batch:
        for member in members:
            batch.put_item(Item=member)
    return len(members)
