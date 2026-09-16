# Deployment verification — 7 September 2026

This is a historical record of the retired rama deployment. Its 44 Terraform
resources were deleted on 12 September 2026. See [cleanup record](rama-jso-cleanup.md)
and [active JSO deployment](jso-deployment.md) for current information.

Application: **https://d3l7736mdenjum.cloudfront.net**

Administrator: `jso_admin@org.in`, using the existing Cognito account and its configured password. No password is stored in the repository and no invitation email was sent.

| Output | Deployed value |
| --- | --- |
| AWS profile / region | `rama` / `us-east-1` |
| CloudFront distribution | `E31AY0XXRNNOD0` |
| API | `https://pajbhcqp9g.execute-api.us-east-1.amazonaws.com` |
| Webhook | `https://pajbhcqp9g.execute-api.us-east-1.amazonaws.com/webhooks/neetform` |
| Cognito pool (existing) | `us-east-1_7lXAB7FYk` |
| Cognito SPA client | `29v92ecqm5ssc9f2cpgbkin9kr` |
| Application access group | `profile-library-users` |
| Profile table | `profile-library-prod-profiles` |
| Jobs / leases table | `profile-library-prod-jobs` |
| Document bucket | `profile-library-prod-docs-08280d0d38e4606d3694f2ef41` |
| Frontend bucket | `profile-library-prod-web-e2219464ae61f6265eab1ec3de` |
| Neeto secret name | `profile-library-prod/neetoform` |

## Completed verification

- 35 backend tests; 11 frontend tests; TypeScript and Vite builds. Terraform validation and apply succeeded; the final plan reports no changes.
- Local mock browser: login, sample profiles, search, detail, PDF popup, mobile layout.
- Local HTTP browser: login, Python API, Sync Now against paginated mock Neeto, dynamic theme filtering, detail.
- AWS: actual Cognito SRP login, JWT denial for anonymous requests, authenticated list/detail, exact-origin CORS, invalid HMAC rejection, valid webhook acceptance and worker processing.
- AWS: a fictional PDF was downloaded from a private signed source, written to encrypted private S3, and registered in DynamoDB. Duplicate delivery updated one profile without re-uploading the document.
- AWS: 15-minute presigned viewing and attachment downloads worked; anonymous S3 access was denied; mobile detail UI and logout worked.
- AWS: S3 public access blocks/encryption, Python 3.12 runtime, Secrets Manager configuration, and CloudWatch status logs were checked. Logs contained neither the fixture email nor signed source URLs.

Randomly identified fictional AWS verification records and PDFs were removed after testing. **At that initial verification, zero real profiles had been imported.** Local sample fixtures remain in the repository.

## Real Neeto connection and attachment recovery — 8 September 2026

The real Neeto API key has since been configured securely in Secrets Manager. Historical synchronization now reads 52 submissions. Attachment downloads were initially blocked because only the private verification bucket's hostname was allowed. The live Terraform configuration now also permits the verified source `app.neetoform.com` and its redirect destination `neeto-form-production-v3.s3.amazonaws.com`.

Recovery completed for all 52 submissions: 32 PDFs were stored in private S3, while 20 first attachments were rejected as non-PDF files (14 Word documents, 5 JPEGs, and 1 PNG). All profile metadata is retained. The current version requires PDF documents; it does not convert Word documents or images.

To replace or rotate the API key later, run `AWS_PROFILE=rama .venv/bin/python scripts/configure-secrets.py`. See [NeetoForm setup](neetform-setup.md) for signing-secret and field-mapping configuration. This recovery verifies the Neeto API import. Delivery from the form’s own configured webhook has not been verified; synthetic HMAC delivery was verified separately.

## Support mapping — 8 September 2026

Support now maps to the exact form label `I'm willing to support this casue by`. All 52 submissions were resynchronized; 26 have an answer in that column. Selected answers are preserved in `supportRaw` and displayed by the existing profile list/detail views. Missing source answers remain blank.

## Account-specific deployment choices

The existing pool is in us-east-1, so the live deployment uses that region. The reusable Terraform default remains eu-north-1. This AWS account has a Lambda concurrency quota of ten and cannot reserve a worker execution. DynamoDB leases protect profile/job writes without requiring a quota increase. No EC2, VPC, NAT gateway, queue, or container is created by this Terraform stack.

## Legacy retirement

The old `jso-candidate-library` CloudFormation stack was confirmed to contain zero profiles and retirement was requested after the new site passed live verification. Its shared Cognito pool is external to the old stack and is preserved. The old encrypted 30-GB disk `vol-0e4611804b09a4e0b` has `DeleteOnTermination=false` and is retained; it continues to incur storage charges. The older external configuration secret and ECR image archive are not managed by the new Terraform stack.

At the final verification, the legacy stack status was `DELETE_IN_PROGRESS`; no deletion failure was reported.

Check retirement status with `aws cloudformation describe-stacks --stack-name jso-candidate-library --profile rama --region us-east-1`. A missing stack after deletion completes is expected. Retained disks/archives need a separate retention decision; they are not automatically deleted.


Theme import now reads the JSO custom column by its configured `field_id` and
`data.value`. All 52 stored themes were compared with the source: 26 populated,
26 missing (displayed as Other). Backend regression suite: 40 passed. Document
sync warnings use soft red styling on cards and profile details.

## Separate member details table (2026-09-08)

Created `jso-member-details` in `us-east-1` using the existing `rama` deployment
profile. Terraform applied one table addition with no changes or deletions to
existing resources. The table uses the string partition key `Email`, on-demand
billing, encryption, point-in-time recovery and deletion protection.

The 19-column active-member importer is ready at
`scripts/import-member-details.py`; see [setup instructions](google-sheets-setup.md#separate-member-details-table).
A one-time legacy import populated 199 active members on 2026-09-08.
That import tooling has since been retired; current Members sync uses Neetoform.
All 199 records were read back consistently and matched all 19 expected attributes
with zero mismatches. The workbook contains 200 members; Excel row 92 was skipped
because its email is blank. The leading Status column supplies membership status;
the duplicate approval Status column is excluded. Emails are normalized and unique.
The application remains on its existing profile table.

## Members application section (2026-09-08)

Deployed the Members navigation tab, searchable paginated directory and structured
member detail view at `/members`. The API reads `jso-member-details` independently
of Profiles. Both new API routes use the existing Cognito authorizer, access group
and read-only DynamoDB permissions. Members displays membership IDs, contact,
background, contribution and source history; Role and Role Title are omitted.

Validation: 56 backend tests, 14 frontend tests and the production build passed.
Read-only invocations of the deployed Lambda verified 199 active members, detail
lookup, email search and the second page. Existing Profiles still returned 54
records. Both public Members endpoints returned 401 without a token. CloudFront's
SPA routing was extended for member detail URLs containing dotted email addresses.

## Member pictures and membership ID display (2026-09-08)

Deployed Unique ID as the displayed Membership ID on Members cards and details;
the original Membership ID attribute is preserved. Areas of Interest now appears
only after opening a member. Imported 123 images, including two HEIC photos, from
the Excel File Upload column into private S3. Another 63 members have no upload
and 13 uploads could not be used as portraits. All 199 member records retain their
other details, with uploaded-file references added using conditional updates.
Pictures display on cards and details, with initials as the fallback.

57 backend tests, 14 frontend tests and the production build passed. The browser
image policy now permits only the app's private document bucket hostnames in
addition to its existing sources.

## Member country filter (2026-09-08)

Deployed the Country dropdown on Members. Country aliases are grouped for filtering
without modifying stored values. Selection combines with search, resets pagination,
and is kept in the URL. All countries clears the filter; Not specified includes
missing countries. The backend returns options from the entire active directory.

58 backend tests, 15 frontend tests and the production build passed. Read-only live
checks verified 199 total members, 4 matching Sweden, 50 matching United States,
32 options including Not specified, combined search, and filtered pagination.

## Inline profile PDF preview (2026-09-08)

Deployed automatic inline PDFs near the top of profile details, using each profile's
signed document link. Reload, open separately and download controls are available,
and preview links renew before expiry. Members pages are unchanged. CloudFront's
frame policy permits only self and the private document bucket hosts.

17 frontend tests and the production build passed. A read-only live check verified
a profile-specific signed URL, inline disposition, valid PDF bytes, and matching
frame policy. Native PDF rendering depends on the user's browser; open/download
controls provide a fallback.
