# Google Sheets member directory

The manual **Sync Now** action can use the member directory instead of Neeto.
Set `GOOGLE_SHEET_ID=1E_XOZfm_mEYONX3tbW3xs-QH4RUN6kXr` and
`GOOGLE_SHEET_GID=1259657163`. In Terraform use `google_sheet_id` and
`google_sheet_gid`; rebuild the backend package with its updated requirements.
Leave the sheet ID empty to keep the original Neeto sync.

## Access

Enable the Google Sheets and Google Drive APIs in the service account's Google
Cloud project. Share the spreadsheet and uploaded photo files (or their parent
folder) with the service account's `client_email` as a viewer. Files remain private.

For local development, put the service-account JSON in the ignored `data/`
directory and set `GOOGLE_APPLICATION_CREDENTIALS` to its absolute path in `.env`.
Do not paste keys into chat or commit them. The local API is a development-only,
loopback server and stores imported profiles in memory until it exits.

For AWS, add `GOOGLE_SERVICE_ACCOUNT_JSON` as a JSON-encoded string to the existing
server integration secret, preserving its other keys. No credentials belong in
Terraform variables, frontend environment variables or the browser.

## Matching and visibility

Emails are trimmed and case-folded for identity. New members get an internal UUID
derived from the email; the spreadsheet's Unique ID is retained only as source
metadata. A matching existing profile retains its UUID and PDF. Existing duplicate
profiles are retained but hidden using a merge marker. Re-running sync updates the
same member. Changing an email creates a new identity; it is not inferred as a rename.

Only `Status` equal to `Active` (ignoring case and whitespace) is visible. New
inactive rows do not create profiles; an inactive row hides an already imported
member, including its detail and document endpoints. If duplicate email rows have
conflicting statuses, an inactive row wins. For same-status duplicates the first
active row or last inactive row supplies the details.

When Sheets mode is enabled, unmatched legacy Neeto profiles are hidden and Neeto
webhooks are disabled so they cannot override the directory. A member removed
entirely from the sheet is not automatically deleted or deactivated: set their
status to Inactive before removing the row and complete a sync. Avoid editing or
sorting the sheet during a sync because checkpointed batches read the live sheet.

## Profiles and photos

All 22 supplied columns map to profile identity or structured membership, contact,
background, contribution and submission sections. Membership IDs remain strings,
preserving leading zeros. Blank values display as Not provided.

File Upload supports Google Drive links to JPEG, PNG or WebP photos; the first
supported image is decoded, resized and stored privately as JPEG with metadata
removed. The browser receives a temporary signed URL on the detail response.
PDFs and other non-image uploads are not converted to portraits. Missing photos
show initials. Unsupported or inaccessible uploads retain the member and report
a partial sync for retry. Existing PDFs remain available separately.

API references: [Sheets values.get](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get),
[Drive downloads](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

## Separate member-details table

Terraform also manages `jso-member-details`, an on-demand, encrypted table with
point-in-time recovery and deletion protection. Its string partition key is
`Email`, trimmed and case-folded. It is separate from the application's existing
profile table; creating or importing this table does not switch the app's source.

The standalone importer copies exactly these 19 attributes: Full Name, Email,
Phone, Country, City/Place, Address, Membership ID, Status, Educational Background,
Professional Experience, Areas of Interest, Skills/Expertise, Motivation, Support
Type, Comments, Submitted On (Earliest), Number of Submissions, Sources, Unique ID.
All values are stored as strings, preserving formatted dates, phone prefixes and
leading zeros. Role, Role Title and File Upload are excluded.

Preview the complete sheet without writing or printing personal information:

```bash
.venv/bin/python scripts/import-member-details.py --credentials /absolute/path/service-account.json
```

Add `--apply` to upsert the validated active rows into AWS. The command defaults
to the existing deployment's `rama` profile and `us-east-1` region; override with
`--profile` and `--region` if needed. Missing columns, invalid active-member emails
and conflicting active duplicates stop the import before any writes. An inactive
duplicate suppresses that email. Re-imports replace records by email without
creating duplicates. The importer does not delete existing records for removed
or subsequently inactive source rows; it is an upsert import, not a live mirror.
An interrupted AWS batch may have partially written records; rerun to finish.

### Member pictures and displayed IDs

Members displays `Unique ID` under the Membership ID label, while preserving both
original source columns in DynamoDB. Blank Unique IDs display Not assigned.

The production member directory imports member details and photos directly from
Neetoform using **Members → Sync Now**. See [member sync](member-neeto-sync.md).
No local workbook or separate photo-import command is required.
