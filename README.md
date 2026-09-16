# JSO Community Portal

The JSO application brings **Idea Incubation**, **Members**, and **Sambhav** into one private portal with a shared login and member directory. The repository and AWS resource names retain the original `profile-library` naming.

**Live application:** https://dse76eldn9xf5.cloudfront.net

**Deployment:** AWS profile `jso`, account `223885744552`, region `us-east-1`, Terraform workspace `jso`.

The former JSO deployments in the `rama` account are retired. Use the JSO workspace and configuration below for this application; older Rama deployment records are historical. See [current deployment notes](docs/jso-deployment.md) and [Rama cleanup](docs/rama-jso-cleanup.md).

## Current features

### Login and approval

- Separate login and signup pages with **Welcome JSO** branding; the signed-in header uses the enlarged JSO logo.
- Google authentication and email/password signup through the existing Amazon Cognito user pool. Email signup supports Yahoo and other email providers.
- Email/password users confirm their email using the emailed verification code. Signup includes resend and verification-resume options.
- New users must receive administrator approval through the `profile-library-users` Cognito group before accessing application data. Signing in or appearing in the member directory does not itself grant access.
- Approved users share the same application access. Member personal information has an additional ownership check; Sambhav editing is available to all approved users.

### Idea Incubation

The former **Profiles** section is now **Idea Incubation**. Search and filter synchronized submissions, view their details, preview PDFs inline, and open or download private documents. Existing `/profiles` API paths and detail links remain supported.

**Sync Now** imports and refreshes NeetoForm submissions asynchronously. Authenticated webhooks can also import submissions. Failed or unsupported document transfers retain submission metadata and any previous PDF. Profile synchronization does not delete profiles or documents when a source submission disappears.

### Members

- Search active members, filter by country, and open structured member details and private photos.
- **Sync Now** on Members imports the full configured NeetoForm member form, independently of Idea Incubation sync.
- Once a complete source read is verified, reconciliation deletes members from DynamoDB when their email no longer exists in that source form. It only deletes records belonging to that form; manual records and other forms are preserved. Incomplete or failed source reads prevent deletion, and concurrent changes are protected.
- A member can edit their own supported personal information when their verified login email matches the member record. The API rejects edits to another member. Email, membership identifiers, source fields, and other protected fields cannot be changed through this editor.
- Personal edits are stored as overrides in DynamoDB, survive later synchronization, and are not written back to NeetoForm.
- There is no Excel workbook dependency. Google Sheets remains an optional integration, not the active JSO member source.

The **Map** option beside **Your Community / Members** shows country intensity based on member counts. Click a country to filter the member list. Search affects map counts; counts are calculated before pagination. Country aliases are normalized, with an explicit country at the end of an address used as a fallback. Missing locations are reported as unmapped. Multi-country members can count in more than one country.

Map geometry is bundled locally from Natural Earth. No external geocoding service receives member addresses, and the map does not plot precise street locations. See [member synchronization](docs/member-neeto-sync.md) and [map behavior and data](docs/member-map.md).

### Sambhav

Sambhav has **nine domains, exactly three idea slots per domain, and 27 total slots**. Domain cards show number, title, description, status, idea slots, and participating-member count. Counts deduplicate leads, co-leads, and interested members within each domain.

| Code | Domain | Slug | Source page metadata |
| --- | --- | --- | --- |
| 01 | FinTech & Financial Inclusion | `fintech-financial-inclusion` | 6 |
| 02 | AI-Driven Skills Mapping & Entrepreneurship | `ai-skills-mapping-entrepreneurship` | 7 |
| 03 | Primary, Middle & School Education | `primary-middle-school-education` | 8 |
| 04 | Higher Education, STEM & Research | `higher-education-stem-research` | 9 |
| 05 | Content Creation, Media & Public Outreach | `content-media-public-outreach` | 10 |
| 06 | Community Policy, Governance & Social Research | `community-policy-governance-social-research` | 11 |
| 07 | Healthcare & Public Health | `healthcare-public-health` | 12 |
| 08 | Agriculture, Environment & Sustainability | `agriculture-environment-sustainability` | 13 |
| 09 | Engineering, Industrial & Vocational Skill Development | `engineering-industrial-vocational-skills` | 14 |

Source page numbers are metadata and are not appended to displayed titles. Domain names, slugs, ordering, and slot identifiers are fixed. Idea IDs run from `01-01` through `09-03`.

Select **Edit domain and ideas** on a domain or idea page to update:

- Domain description and status.
- Each idea's title, short summary, detailed description, vision, and status.
- Lead, co-lead, and interested members selected from the existing active member directory.

Updates persist in DynamoDB with timestamps and editor identity. Version checks reject stale saves to protect newer edits. Unpopulated slots start as **Not started**, without invented content, members, or dates.

Each idea supports multiple PDF attachments under **Vision documents**, **Project details**, **Member profiles**, and **Other documents**. The limit is **20 MB per PDF and 30 PDFs per idea across all categories**. Password-protected or unreadable PDFs are rejected. Text edits preserve attachments; this release supports adding and downloading attachments, without removal/replacement controls.

PDFs use the existing private, encrypted S3 bucket. Five-minute signed upload forms send files to staging; the backend validates the bytes before publishing a separate final copy and saving metadata. Published files cannot be overwritten by replaying a staging upload. Downloads require application authorization and use five-minute signed links. Unfinished staging uploads expire after one day. PDF validation is not malware scanning.

See [Sambhav requirements and storage](docs/sambhav-requirements.md).

## Application routes

| Route | Page |
| --- | --- |
| `/login`, `/signup` | Sign in, create an account, and confirm email |
| `/` | Idea Incubation |
| `/profiles/{profileId}` | Submission details and PDF preview |
| `/members` | Member directory |
| `/members?view=map` | Member map and filtered directory |
| `/members/{email}` | Member details; URL-encode the email |
| `/sambhav` | Nine-domain program overview |
| `/sambhav/domains/{domainSlug}` | Domain details with three idea sections |
| `/sambhav/domains/{domainSlug}/ideas/{ideaId}` | Individual idea details |

All community pages use the existing authentication and approval guard.

## Architecture and storage

React, TypeScript, and Vite build the frontend served by CloudFront from a private S3 bucket. Cognito authenticates users; API Gateway validates access tokens, and the Python 3.12 API Lambda enforces application access. A worker Lambda handles synchronization and signed webhooks. Synchronization returns `202` immediately, checkpoints its progress, and exposes job status for browser polling.

| Resource | Purpose |
| --- | --- |
| `profile-library-prod-profiles` | Idea Incubation submission metadata |
| `profile-library-prod-jobs` | Synchronization jobs and checkpoints |
| `jso-member-details` | Existing email-keyed member directory and personal edits |
| `profile-library-prod-sambhav` | Saved domain/idea metadata and expiring upload tickets |
| Existing private document S3 bucket | Submission PDFs, member photos, and Sambhav PDFs |
| Separate private frontend S3 bucket | Compiled frontend assets |
| Secrets Manager | NeetoForm credentials and Google OAuth configuration |

Sambhav reuses the existing application, authentication, member directory, API, Lambda, S3 bucket, and Terraform deployment. Its metadata table uses on-demand capacity, encryption, point-in-time recovery, and TTL for upload tickets. The application uses ZIP-packaged Lambdas: **no ECR images, EC2 servers, containers, VPC, or NAT gateway are required**.

Costs depend on requests, storage, downloads, authentication usage, backups, logs, and Secrets Manager. The design avoids always-running application servers and provisioned Sambhav database capacity. Stored PDFs and backup/log retention still incur charges; this README does not represent a measured monthly AWS bill or a guaranteed price.

## Prerequisites and local development

Use Node.js 22.12+, npm, Python 3.12+, Terraform 1.10+, and AWS CLI v2. Local mock mode needs no AWS account or integration credentials.

```bash
make setup
make dev
```

Open http://localhost:5173. Mock mode accepts nonempty demo credentials and provides fictional profile data and a sample PDF. Sambhav edits in mock mode are temporary, and PDF uploads require the deployed backend. Production deployment explicitly disables mock mode.

To exercise the local Python backend and mock Neeto server, run these in separate terminals:

```bash
make mock-neeto
```

```bash
make backend
```

```bash
VITE_USE_MOCK_API=false VITE_USE_LOCAL_API=true make dev
```

The local backend binds to loopback and uses in-memory data; it is not a substitute for verifying Cognito, DynamoDB persistence, or S3 uploads. See [local development](docs/local-development.md).

### Test and build

```bash
make test
make build
```

With the local services running, the existing integration smoke check is:

```bash
.venv/bin/python scripts/local-smoke.py
```

Backend tests use mocked AWS clients and Moto. Frontend and backend coverage includes authentication, approval, profiles, member access and reconciliation, maps, Sambhav editing, attachment validation, and error handling. Lambda packaging targets Python 3.12.

## Deploy updates to the active JSO application

Use the existing JSO Terraform state and reviewed `infrastructure/terraform/jso.tfvars`. State and private deployment configuration are not substitutes for repository examples; obtain the existing deployment files when setting up another operator's checkout.

```bash
export AWS_PROFILE=jso
export TF_WORKSPACE=jso
aws sts get-caller-identity --query Account --output text
terraform -chdir=infrastructure/terraform workspace show
```

Confirm account **223885744552** and workspace **jso** before continuing. Do not initialize a replacement stack or use the retired default/Rama configuration to update this application.

```bash
make test
./scripts/build-backend.sh
terraform -chdir=infrastructure/terraform init -input=false
terraform -chdir=infrastructure/terraform validate
terraform -chdir=infrastructure/terraform plan \
  -var-file=jso.tfvars -out=../../.build/jso-update.tfplan
```

Review the plan, including data retention and resource replacements, then apply that exact plan and deploy the frontend:

```bash
terraform -chdir=infrastructure/terraform apply ../../.build/jso-update.tfplan
./scripts/deploy-frontend.sh
```

The frontend script builds using the selected workspace's outputs, uploads assets to S3, and invalidates CloudFront. For frontend-only changes, run frontend tests and that script with the same profile/workspace exports.

The generic `make deploy` / `scripts/deploy.sh` path does not explicitly select `jso.tfvars`; use the commands above for the current deployment. See [JSO deployment notes](docs/jso-deployment.md) for deployment history and verified behavior, and [general deployment guidance](docs/deployment.md) for retention and state management.

## Approve and manage users

Users can sign up with Google or with email and password at the live application's signup page. Native email signup requires a password of at least 12 characters including uppercase, lowercase, a number, and a symbol, followed by email-code verification.

To approve an account in the AWS Console, select **us-east-1 → Cognito → user pool `us-east-1_RbUqJHia7` → Users**, open the user, and add them to **`profile-library-users`**. Google users may have a generated Cognito username: use the actual username shown in the pool, not an assumed email username.

Alternatively, from a checkout with the JSO state:

```bash
export AWS_PROFILE=jso
export TF_WORKSPACE=jso
profile_pool=$(terraform -chdir=infrastructure/terraform output -raw cognito_user_pool_id)
profile_region=$(terraform -chdir=infrastructure/terraform output -raw aws_region)
profile_group=$(terraform -chdir=infrastructure/terraform output -raw required_group)

aws cognito-idp admin-add-user-to-group \
  --user-pool-id "$profile_pool" \
  --username 'ACTUAL_COGNITO_USERNAME' \
  --group-name "$profile_group" \
  --region "$profile_region"
```

Ask the user to sign out and back in after approval to refresh access claims. No deployment is needed. Adding a member through synchronization does not create or approve a Cognito login.

For an administrator-created native account, `./scripts/create-user.sh reviewer@example.com` creates the user, grants the configured group, and prompts privately for a permanent password. It suppresses invitation emails and **also resets the password if the user already exists**. Use the group command above to approve an existing account without changing its password. Administrator-created accounts must also have a verified email before using member self-editing.

For native-account password administration, use `scripts/set-user-password.py` with the pool, actual username, and region; it prompts without echoing the password. Google-account passwords are managed by Google. See [Google authentication and email signup setup](docs/google-auth-setup.md).

## Integration and environment configuration

### NeetoForm

The active workspace API base is `https://jso.neetoform.com/api/external/v1`.

| Import | Form ID | Behavior |
| --- | --- | --- |
| Idea Incubation | `4c47b1a6-144c-44ea-a6ce-0a151cdcb630` | Import/refresh metadata and supported PDFs |
| Members | `bf924943-de8b-4c15-9fd6-eebaa63e8b1a` | Full unfiltered form sync and safe deletion reconciliation |

The integration reads `GET /forms/{form_id}/submissions` using `X-Api-Key` and pagination. Configure field mappings and permitted attachment hosts in the JSO Terraform configuration. Do not use a filtered admin-page URL as the member reconciliation source.

With `AWS_PROFILE=jso` and `TF_WORKSPACE=jso` exported, update Neeto credentials through the hidden prompt:

```bash
.venv/bin/python scripts/configure-secrets.py
```

Credentials remain in Secrets Manager. For webhooks, use Terraform's `webhook_url` and the signing secret from the Neeto secret; signature validation uses the original request bytes. See [NeetoForm configuration](docs/neetform-setup.md) and [member sync mappings and deletion safeguards](docs/member-neeto-sync.md).

### Google OAuth

Google authentication uses the existing Cognito hosted domain. The configured Google redirect URI is:

```text
https://profile-library-prod-223885744552.auth.us-east-1.amazoncognito.com/oauth2/idpresponse
```

The OAuth secret is server-side in Secrets Manager; never place it in frontend environment variables or source control. Follow [Google authentication setup](docs/google-auth-setup.md) for Google Console and Cognito configuration.

### Configuration files

[.env.example](.env.example) and [frontend/.env.example](frontend/.env.example) document local defaults, which are not the production JSO region/configuration. Production frontend values come from Terraform outputs, including API URL, Cognito pool/client/region, required group, and Google OAuth settings.

Backend settings include profile/job/member/Sambhav table names, the document bucket, Neeto form and mapping settings, Cognito authorization settings, file limits, and signed-link expiry. See [backend configuration](backend/src/config.py) and [Terraform variables](infrastructure/terraform/variables.tf) for the full configuration. Secret values belong in Secrets Manager or ignored local credentials, never in `VITE_` variables.

Optional Google Sheets integration is documented in [Google Sheets setup](docs/google-sheets-setup.md). No spreadsheet workbook or Excel import is required for the current application.

## API overview

These paths are relative to the deployed API, not the frontend page routes. All require approved application access except the separately signed webhook.

| Method and path | Purpose |
| --- | --- |
| `GET /profiles`, `GET /profiles/{id}` | Search/list and retrieve submissions |
| `GET /profiles/{id}/document` | Temporary document URL; supports `disposition=attachment` |
| `POST /sync`, `GET /sync`, `GET /sync/{jobId}` | Start/check Idea Incubation synchronization |
| `GET /members` | Search, country filtering, pagination, and map counts |
| `GET /members/detail?email=...` | Retrieve an active member |
| `POST /members/detail?email=...` | Update the verified user's own supported fields |
| `POST /members/sync`, `GET /members/sync`, `GET /members/sync/{jobId}` | Start/check member synchronization |
| `GET /sambhav` | Program domains and saved content |
| `GET /sambhav/domain?domain=...`, `POST /sambhav/domain?domain=...` | Read/save domain and idea metadata |
| `POST /sambhav/upload?domain=...` | Issue a signed PDF staging upload form |
| `POST /sambhav/upload/complete?domain=...` | Validate and attach an uploaded PDF |
| `GET /sambhav/document?domain=...&idea=...&document=...` | Authorized attachment download link |
| `POST /webhooks/neetform` | Raw-body HMAC-authenticated Neeto webhook |

Idea Incubation signed document URLs normally expire after 15 minutes; Sambhav links expire after five minutes. Manual synchronization can also be started using `scripts/sync.sh`, which prompts privately for an access token.

## Security and troubleshooting

S3 buckets block public access. CloudFront reads frontend assets through its origin access configuration; documents and member photos use temporary signed URLs. JWT validation, application group checks, ownership checks for member edits, scoped IAM, restricted CORS, encrypted storage, attachment host checks, and PDF size/content validation protect application data. See [security details](docs/security.md).

- **Awaiting approval / API 403:** add the actual Cognito user to `profile-library-users`, then sign out and back in.
- **Cannot edit member details:** confirm that the login email is verified and matches the member's email. Approval does not allow editing someone else's personal record.
- **Member missing after sync:** check the full source form and normalized email. Source-owned records absent after a complete source read are intentionally removed.
- **Sync fails or a document is missing:** check the safe job error, secret configuration, source field mappings, file type/size, and permitted attachment hosts. Failed transfers can leave metadata visible without a PDF.
- **Sambhav save conflict:** reload the latest domain, reapply your changes, and save again.
- **PDF upload fails:** use a readable, unencrypted PDF within 20 MB and the 30-file idea limit. Retry to obtain a fresh upload form if it expired.
- **Terraform state/output errors:** restore access to the existing JSO state and select workspace `jso`; do not create another deployment to manage users or repair frontend configuration.

## Repository and operating guides

- `frontend/`: application pages, authentication, shared components, program definition, bundled map data, and UI tests.
- `backend/src/`: API/worker handlers, integration services, authorization, persistence, and Sambhav seed structure.
- `backend/tests/`: backend tests and fixtures.
- `infrastructure/terraform/`: existing AWS deployment resources.
- `scripts/`: builds, deployments, integration configuration, imports, and local checks.
- `docs/`: [current deployment](docs/jso-deployment.md), [architecture](docs/architecture.md), [local development](docs/local-development.md), [authentication](docs/google-auth-setup.md), [member sync](docs/member-neeto-sync.md), [member map](docs/member-map.md), and [Sambhav](docs/sambhav-requirements.md).

Infrastructure removal is a separate operation: `scripts/destroy.sh` requires confirmation, and data resources have retention/deletion protections. Review [deployment and retention guidance](docs/deployment.md) before any teardown. Historical [Rama deployment](docs/live-deployment.md) and [legacy deployment](docs/legacy-deployment.md) documents do not describe the active JSO endpoint.
