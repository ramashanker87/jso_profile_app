# Jobs

The `/jobs` page is available from the main navigation to approved users.

1. Paste an `http://` or `https://` job-opening link.
2. Optionally add a job title/company name and a short description (up to 2,000 characters).
3. Optionally select **Candidate profiles** and/or **Job profiles**. Each job accepts
   up to 10 PDF attachments in total, up to 20 MB each.
4. Select **Add job**. The listing is saved first, then the selected files upload.
5. Open the original job website or use an attachment's **Download** button.
6. When a vacancy closes, select **Delete closed job**, then **Confirm delete**.
   Cancel keeps the listing.

All approved users can share links, download attachments, and remove closed
listings. Attachments are visible to all approved JSO users, including candidate
profiles. Deletion removes the community listing and attempts to remove its
published attachments; it does not change the posting on the employer's website.
Closing a job is a manual action; external websites may require their own login.

If an upload fails, the saved listing and successful attachments remain visible.
Use **Retry attachments** to continue with the remaining files without creating
another job, or **Keep job without remaining attachments** to finish. An unwanted
pending file can also be removed from the selection. Keep the page open while
retrying: selected browser files and retry state are not retained on reload.

The application stores the supplied link, title, description, attachment metadata,
creation time, and creator's Cognito subject in DynamoDB. The linked website is
not scraped, embedded, or cached. If no title is supplied, its hostname labels the
listing. Re-adding the same normalized URL returns a duplicate error; distinct
tracking URLs can still represent the same vacancy.

## API and storage

| Method and path | Behavior |
| --- | --- |
| `GET /job-openings` | List shared openings, newest first, plus `uploadsEnabled` |
| `POST /job-openings` | Create from `{ "url": "https://example.org/jobs/123", "title": "Optional title", "description": "Optional summary" }` |
| `DELETE /job-openings/{id}` | Remove the listing and attempt attachment cleanup; repeat deletion succeeds |
| `POST /job-openings/{id}/upload` | Create a signed upload form from `{ "category": "candidate-profile", "fileName": "profile.pdf", "size": 1234 }`; category can also be `job-profile` |
| `POST /job-openings/{id}/upload/complete` | Validate and publish an uploaded PDF using `{ "uploadId": "..." }`; return the updated job |
| `GET /job-openings/{id}/attachments/{documentId}` | Return an authorized, five-minute signed download URL |

All routes use the existing Cognito authorizer and application-group checks.
Upload tickets are bound to the requesting Cognito subject and the specific job
creation, so an old ticket cannot attach a file to a deleted/recreated listing.
Links must use HTTP(S), contain no credentials, and be at most 4,000 characters.
Titles are limited to 200 characters. External links use `noopener noreferrer`;
React renders descriptions and filenames as text.

The dedicated `profile-library-prod-job-openings` DynamoDB table is distinct from
`profile-library-prod-jobs`, which tracks synchronization. It uses on-demand
billing, encryption, point-in-time recovery, and table deletion protection. Job
IDs are hashes of normalized URLs. Conditional writes prevent duplicate creation,
concurrent attachment overwrites, and resurrection of a deleted listing. Existing
jobs without descriptions or attachments remain compatible; no data migration is
required. Listing scans every DynamoDB page and excludes upload-ticket records.

## Private S3 attachments

PDF bytes are stored in the **existing private document S3 bucket**:

- `job-openings/pending/<uploadId>.pdf`: temporary browser uploads.
- `job-openings/documents/<jobId>/<generatedId>.pdf`: published, validated files.

The browser uploads directly with a five-minute signed POST form restricted to an
exact key, declared size, PDF content type, and AES256 server-side encryption.
The backend checks actual size and PDF readability, rejects encrypted/unreadable
PDFs, and writes validated bytes to a separate final key. Replaying a staging
upload cannot overwrite a published attachment. Validation is not malware scanning.

Successful confirmation is idempotent while its ticket is retained. The browser
reuses confirmation tickets when a completed transfer's confirmation fails, and
conditional writes protect concurrent saves. Staging objects expire after one day;
upload-ticket metadata expires after one hour via DynamoDB TTL. The backend
checks expiry itself because TTL removal is asynchronous. Job records have no TTL.

List/create responses omit private object keys. Download URLs are created only
for attachments on an existing job after authorization, expire after five minutes,
and request attachment disposition. Deleting a job removes its metadata first,
then attempts S3 deletion. Cleanup failures emit `job_attachment_cleanup_failed`;
an uncertain database save emits `job_attachment_save_uncertain` and retains the
validated file because the write may have committed. These cases can leave private
unreferenced files requiring operator cleanup. A previously issued download link
can remain valid until expiration if its object could not be removed.

## Development and deployment

The browser demo supports descriptions, temporary attachment blobs, and downloads
until reload; it does not send files to S3. The local Python API supports job
metadata in memory and reports `uploadsEnabled: false` because it has no S3 upload
adapter. Production stores metadata in DynamoDB and attachments in S3. Backend
attachment tests exercise both repositories and S3 using Moto without AWS credentials.

Deploy backend/infrastructure **before** the frontend. This update adds authenticated
upload/download routes, DynamoDB read permission and ticket TTL, scoped S3 access
under `job-openings/`, and an additional staging-expiration rule in the document
bucket's existing lifecycle configuration. Existing document-bucket CORS allows
signed POST uploads from the configured frontend origin. See the README's full
JSO deployment instructions; a frontend-only deployment is insufficient.
