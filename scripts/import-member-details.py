#!/usr/bin/env python3
"""Preview by default; --apply upserts active members into jso-member-details."""
import argparse
import json
import os
from pathlib import Path
import sys
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import boto3
from src.config import Settings
from src.errors import AppError
from src.services.sheets_service import GoogleSheetsClient
from src.services.member_details_service import MEMBER_COLUMNS, prepare_members, import_members


class FileCredentials:
    def get(self):
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", required=True, help="Local service-account JSON path")
    parser.add_argument("--profile", default="rama")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-missing-email", action="store_true", help="Leave rows without email unimported; report their row numbers")
    args = parser.parse_args()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(args.credentials).resolve())
    settings = replace(Settings(), google_sheet_id="1E_XOZfm_mEYONX3tbW3xs-QH4RUN6kXr",
                       google_sheet_gid="1259657163")
    client = GoogleSheetsClient(settings, FileCredentials())
    # Read one complete snapshot, avoiding changes between paginated requests.
    rows = client.rows(required_columns=MEMBER_COLUMNS)
    source_count = len(rows)
    skipped = [index for index, row in enumerate(rows, 2) if not row.get("Email", "").strip()] if args.skip_missing_email else []
    if skipped:
        rows = [row for row in rows if row.get("Email", "").strip()]
    members = prepare_members(rows)
    print(json.dumps({"table": "jso-member-details", "sourceRows": source_count, "skippedMissingEmailRows": skipped,
                      "activeUniqueMembers": len(members), "mode": "apply" if args.apply else "preview"}))
    if args.apply:
        table = boto3.Session(profile_name=args.profile, region_name=args.region).resource("dynamodb").Table("jso-member-details")
        if table.key_schema != [{"AttributeName": "Email", "KeyType": "HASH"}]:
            raise AppError("Destination table must have Email as its only partition key.")
        imported = import_members(table, members)
        mismatches = 0
        for expected in members:
            actual = table.get_item(Key={"Email": expected["Email"]}, ConsistentRead=True).get("Item")
            mismatches += actual != expected
        print(json.dumps({"imported": imported, "verified": imported - mismatches,
                          "mismatches": mismatches}))
        if mismatches:
            raise AppError("Some stored members did not match the source after import.")


if __name__ == "__main__":
    try:
        main()
    except AppError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
