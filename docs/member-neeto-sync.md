# Members sync from NeetoForm

Current deployment imports the entire form: both status filter settings are empty.
The full-form preview contains 146 submissions and 142 unique member emails.
Duplicate submissions are combined. All imported records are visible in Members;
this does not grant their owners application login access.

The **Members → Sync Now** button imports into `jso-member-details`.
Profiles continues to use its existing form and profile table. Both features
require an approved application account and support Google/password login.

## Source selection

Status filtering is optional. Set both filter values to enable it, or leave both
empty to import all submissions. The earlier filtered configuration was:

- Form: `bf924943-de8b-4c15-9fd6-eebaa63e8b1a`.
- Status field: `f50482c1-c59f-481f-a00b-09e17fdc2ffc`.
- Selected status: `dcbd23d8-e202-43a8-9e91-92317ca22167`.
- Supplied browser segment: `3d311c2d-d5fb-4f0d-93c1-2f930063189d`.

The public Neeto API ignores `segment_id` and `customstatus` query parameters.
When filtering is configured, the importer reads every source page and matches the selected status against
each submission's `field_values`. It does not claim to reproduce additional
saved-segment rules, which are not exposed by the public API. The initial
preview found 146 submissions, 29 matching the selected status, and 28 photos.

## Import behavior

Emails are normalized and used as stable member keys. Duplicate selected
submissions are combined, with newer nonblank answers taking precedence, the
earliest submitted date preserved, and submission count recorded. Invalid
selected email addresses stop validation before returning rows for import.

Mapped data includes name, email, phone, address, country/city, education,
experience, interests, skills, motivation, Unique ID, and the verified custom
Membership ID and Comments columns. Unknown custom fields are not guessed.
Selected records are marked Active for display in the member directory.

Updates preserve other member attributes and existing photos. Blank source
values do not erase existing details. After importing, sync re-reads the entire
form and removes DynamoDB records owned by this form whose normalized email
no longer appears in any submission. Removing one duplicate submission does
not remove a member if another submission still uses that email. Profile records
and records owned by another source are never deleted.

Deletion requires a complete source listing with consistent totals and unique
submission IDs. API errors, incomplete pages, duplicate IDs, changing totals,
and invalid emails stop reconciliation. An explicitly empty form (total zero)
removes all members owned by that form. Status-filter changes alone do not
remove a member: reconciliation always uses the full unfiltered form.

Conditional deletes protect records changed since the table scan. Reconciliation
checkpoints its removed count and resumes if it runs low on execution time.
The Members sync summary shows how many records were removed. Photos remain
in private S3; this feature deletes DynamoDB member records only.

Photos are downloaded only from the existing verified host allowlist, checked
for size and valid image data, resized and stored as JPEG in private S3.
Photo failures keep member details and any old photo, record a warning, and
can be retried with Sync Now. Source fingerprints avoid repeat downloads.

## API and jobs

- `POST /members/sync` starts a Members job.
- `GET /members/sync` returns its latest status.
- `GET /members/sync/{jobId}` polls one Members job.

The jobs table uses `STATE#members` for Members and the existing `STATE` for
Profiles. A Members job cannot be read through the Profiles status endpoint,
and vice versa. Worker leases, checkpointing and asynchronous retries use the
existing sync mechanism; only the worker receives member-table write access.

## Deployment

Use `AWS_PROFILE=jso TF_WORKSPACE=jso`. Configure `member_neeto_form_id`,
`member_neeto_status_field`, and `member_neeto_status_value` in `jso.tfvars`.
The stored Neeto API key is reused. Build the backend, review/apply Terraform
with `-var-file=jso.tfvars`, then run `scripts/deploy-frontend.sh`.

## Full-form import verification — 11 September 2026

The status filter was removed at the user's request. The completed sync stored
142 unique members from 146 submissions, combining duplicate email addresses.
124 photos were saved; four photo imports have warnings and all affected member
details were retained. The other 14 members have no photo upload.

The larger sync exposed AWS Lambda's default recursive invocation cutoff at
16 batches. Terraform now explicitly permits the worker's intentional recursive
batch chain. SyncRunner's pagination and no-progress checks remain enforced.
The interrupted job resumed at its saved checkpoint and completed. A regression
test exercises 142 members across more than 16 worker batches.

## Editing your own member information

An approved user can open their own member details and choose **Edit my
information**. The login account must have a verified email matching the member
email. Other members remain read-only, and the API independently verifies the
Cognito account's subject and verified email before accepting updates.

Editable fields are name, phone, location, education, experience, interests,
skills, motivation, support type and comments. Email, status, membership IDs,
photos and source metadata cannot be changed through this endpoint.

Personal changes are stored in `SelfEdits` with the Cognito subject and edit time.
Directory reads and searches apply these overrides, so Neetoform sync does not
overwrite personal edits. These edits do not write back to Neetoform. Deleting a
submission from Neetoform still removes its member on the next complete sync.

The member directory has no local workbook dependency. Member details and photos
come from the configured Neetoform; personal edits are preserved as described above.
