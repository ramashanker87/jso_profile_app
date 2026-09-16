# AWS jso deployment

This deployment uses AWS profile `jso`, account `223885744552`, region
`us-east-1`, and Terraform workspace `jso`. The original deployment remains in
workspace `default` in a different account. Always specify both the AWS profile
and Terraform workspace when managing this deployment.

Account-specific settings are in the ignored local file
`infrastructure/terraform/jso.tfvars`. This creates a separate Cognito pool;
the original account's user pool and document bucket are not reused.

To update:

```bash
export AWS_PROFILE=jso TF_WORKSPACE=jso
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
(cd frontend && npm test && npm run build)
./scripts/build-backend.sh
terraform -chdir=infrastructure/terraform validate
terraform -chdir=infrastructure/terraform plan -var-file=jso.tfvars -out=../../.build/jso.tfplan
terraform -chdir=infrastructure/terraform apply ../../.build/jso.tfplan
./scripts/deploy-frontend.sh
```

Do not use `scripts/deploy.sh` for this account: it does not pass `jso.tfvars`.
Back up local state in `infrastructure/terraform/terraform.tfstate.d/jso/`
securely along with `jso.tfvars`.

This is a fresh deployment. Existing profiles, members, documents, users and
integration secret values are not automatically migrated from the original
account. Configure integration secrets using `scripts/configure-secrets.py`
with `AWS_PROFILE=jso TF_WORKSPACE=jso`. An administrator can be provisioned
with `scripts/create-user.sh EMAIL` under those same environment variables;
that script prompts locally for a password and suppresses invitation email.

## Deployment verification — 11 September 2026

- Website: https://dse76eldn9xf5.cloudfront.net
- API: https://omf44n1n5j.execute-api.us-east-1.amazonaws.com
- Terraform: 45 resources created; final plan reports no changes.
- Tests: 58 backend and 17 frontend tests passed; production build passed.
- Live checks: homepage and member deep link return HTTP 200; anonymous
  Profiles and Members API requests return HTTP 401. Direct read-only Lambda
  invocations with simulated authorizer claims return HTTP 200 for both lists.
- End-to-end user login has not been verified; administrator provisioning and
  integration secret configuration remain pending.

## Google authentication preparation — 11 September 2026

Google signup/sign-in support and an approval screen are implemented. The
Cognito OAuth domain is provisioned and the browser security policy allows
its token endpoint. The Google provider and button remain disabled until a
Google OAuth client ID and Secrets Manager secret ARN are configured.
See [Google authentication setup](google-auth-setup.md) for the exact callback
URL, credential configuration, and account approval commands.

Validation: 25 frontend tests and the production build passed. Real Google
signup/sign-in cannot be verified until the OAuth credentials are supplied.

## Google signup enabled — 11 September 2026

The Google OAuth secret is now stored in AWS Secrets Manager as
`profile-library-prod/google-oauth`, and Cognito's Google provider is enabled.
The login page at https://dse76eldn9xf5.cloudfront.net/login now displays
**Continue with Google**. The existing application group remains required;
new Google users see Awaiting approval until an administrator grants access.

A live headless browser verified the button, authorization code flow with S256
PKCE, correct Google client ID and callback URL, and arrival at Google's sign-in
page. Signing into a real Google account and completing the token exchange
remain user-assisted verification steps.

Cognito-populated Google endpoint fields are excluded from Terraform drift
checks; client ID, client secret, scopes and attribute mappings remain managed.

## Dedicated login and signup pages — 11 September 2026

The frontend now provides `/login` and `/signup` with account navigation,
Google signup, existing Google/password login, and clear approval guidance.
New account creation uses Google; email/password remains available for existing
accounts. Signup does not change the application access group requirement.

Validation: 27 frontend tests and production build passed. Live desktop and
390-pixel mobile browser checks verified navigation, direct signup URLs, no
horizontal overflow or JavaScript errors, and successful redirect to Google.

## Google session API scope correction — 11 September 2026

Google OAuth access tokens contain `openid`, while Cognito password login tokens
contain `aws.cognito.signin.user.admin`. The API originally required only the
latter, preventing Google sessions from accessing Profiles, Members and Sync.
All eight protected routes now accept either scope when Google login is enabled.
JWT signature, issuer, client, expiry, access-token use and application group
checks remain in place. Password-only deployments keep their original scope.

Validation: 27 backend integration tests passed, all eight live routes were
checked, and the Neeto API returned 56 submissions for the configured form.
The last sync stored all 56 profiles and 36 PDFs; 20 non-PDF documents were
rejected while their profile metadata was retained. A real Google session must
retry Sync Now to confirm the complete browser-to-API flow.

## Members Neeto sync — 11 September 2026

Deployed the independent Members Sync Now button and protected sync endpoints.
The source is form `bf924943-de8b-4c15-9fd6-eebaa63e8b1a`, filtered by status
`dcbd23d8-e202-43a8-9e91-92317ca22167`. See
[Members sync documentation](member-neeto-sync.md) for mapping and segment limits.

The first job imported 29 members and 28 private encrypted JPEG photos with
zero failures. Every mapped nonblank member field was compared with the source.
The second job reported all 29 unchanged with zero failures; S3 modification
times confirmed no photo re-uploads. Profiles retained its 56 records.

65 backend tests, 28 frontend tests and the production build passed. Live
Members, Members sync status and Profiles Lambda calls returned 200, and new
sync status endpoints returned 401 without authentication. Terraform reported
no remaining changes.

## Full-form Members sync — 11 September 2026

Members now imports the unfiltered membership form. Both status settings are
empty. A completed import processed 142 unique members from 146 submissions;
124 photos were stored and four photo warnings retained their member details.
The worker's intentional recursive batch chain is now explicitly allowed so
imports longer than 16 invocations finish. The interrupted import resumed from
its checkpoint. 68 backend tests passed, including optional-filter coverage;
the expanded worker regression checks a 142-member import. Final Terraform
plan reports no changes. The frontend Sync Now button uses this configuration.

## Member deletion reconciliation — 11 September 2026

Members sync now removes DynamoDB members whose email is absent from a complete
read of the membership form. Only records tagged with this form are eligible;
another remaining submission with the same email preserves the member. Failed
or incomplete source reads prevent deletion, and conditional writes protect
records changed concurrently. Existing photo objects remain in S3.

Deployed backend, member-table Scan/DeleteItem permissions and the frontend
removed-count summary. Validation passed: 82 backend tests, 28 frontend tests,
production build and a final Terraform plan with no changes. The live sync
completed with 141 members processed and one stale member deleted, leaving
141 DynamoDB members. Four existing photo warnings retained member details.

## Owner-only member editing — 11 September 2026

Deployed the member detail edit form and authenticated POST /members/detail.
The API reads the Cognito account and requires its subject and verified email
to match the authenticated caller and target member. Only personal fields are
accepted. SelfEdits overrides preserve changes across Neetoform syncs and are
applied to directory searches and display. No updates are sent to Neetoform.

96 backend tests and 30 frontend tests passed, and the production frontend build
succeeded. Live Lambda checks rejected another-member edit (403) and a protected
status-field update (400); API Gateway rejected an anonymous edit (401). These
live checks did not mutate member records. A real signed-in browser save remains
to be exercised by a member; the owner save flow is covered by automated tests.

## Email-and-password signup — 11 September 2026

Enabled Cognito self-registration and deployed email/password signup alongside
Google signup. Users confirm their email with a code, then require administrator
membership in profile-library-users before accessing the application. Signup
supports code resend and resuming verification. Passwords must match the existing
12-character Cognito policy. No automatic group assignment was introduced.

Validation: 33 frontend tests, 96 backend tests and production build passed.
Live Cognito settings confirm self-registration and email verification; live
Lambda calls without the approval group returned 403 for Members and Profiles.
No real signup email was sent during verification, so inbox delivery remains
for the first real signup to confirm.

## Members map — 12 September 2026

Deployed List/Map controls beside the Members heading and a locally hosted world
map shaded by member count. Counts aggregate all active members matching search,
before pagination or country selection. Country clicks filter the cards below.
Country aliases, explicit address country fallback, personal edits, unmapped
entries and multiple-country memberships are supported. No map API key or new
AWS resource was added. See [map documentation](member-map.md).

Validation passed: 99 backend tests, 35 frontend tests, production build and
browser previews at desktop and 390px mobile width without horizontal overflow.
Live API checks returned 141 members across 27 countries with no unmapped entries,
and verified country filtering while preserving all-country map counts.

## Idea Incubation and Sambhav — 14 September 2026

Renamed the Profiles navigation, page heading and return link to Idea Incubation.
Existing submission data and URLs continue to work. Added Sambhav immediately
after Members, at /sambhav behind the existing login and approval guard. It shows
an empty-content message until content is supplied. Navigation wraps on small
screens. All 36 frontend tests and the production build passed.

## Sambhav program structure — 14 September 2026

Replaced the empty Sambhav page with the specified nine ordered domains and
exactly three idea slots per domain (27 total). Added domain and idea detail
routes under /sambhav/domains, using the existing approval guard and visual
components. Each idea displays all required text, member, document and date
fields. Initial content is explicitly unassigned; no member assignments or
source content were invented. Page references remain metadata only. The portal
is read-only and creates no additional backend, database or AWS resources.
See [feature requirements](sambhav-requirements.md).

All 42 frontend tests and the production build passed. Browser checks verified
nine cards, three idea sections, navigation, direct-link reload and mobile
layouts without horizontal overflow.

## Persistent Sambhav editing and PDFs — 14 September 2026

Deployed domain/idea editing and multiple PDF uploads using the existing approved
user group. Metadata is stored in profile-library-prod-sambhav with on-demand
billing, encryption, PITR and upload-ticket TTL. PDFs use the existing private
bucket's sambhav prefix, with one-day expiry only for unfinished staged uploads.
No member data or sync sources are changed. New authenticated endpoints serve
metadata saves and scoped upload/download operations; CSP and S3 CORS permit
uploads only from the application origin.

111 backend tests and 44 frontend tests passed, along with the production build,
Terraform validation and desktop/mobile editor checks. A live test verified
metadata save/reload, unapproved-access rejection, signed POST and CORS, PDF
validation, private download and cross-idea document isolation. Temporary data
was removed and the original domain restored after verification.

## Shared Jobs section — 16 September 2026

Deployed `/jobs` with link-only posting, optional titles, links to job descriptions
on the original website, and confirmed deletion of closed listings. All approved
users can add and remove listings. A dedicated on-demand DynamoDB table,
`profile-library-prod-job-openings`, stores job links independently of sync jobs,
with encryption, point-in-time recovery, and table deletion protection.

Terraform applied four additions (one table and three protected API routes) and
four in-place updates, with no resource deletion. Validation: 144 backend tests,
53 frontend tests, production build, and Terraform validation passed. Direct live
Lambda checks using simulated authorizer claims verified approval enforcement,
creation, persistent listing, duplicate rejection, and deletion; the temporary
verification listing was removed. API Gateway rejected anonymous Jobs access
with HTTP 401. Frontend assets were published and CloudFront invalidation requested.
A real signed-in browser session was not exercised during this deployment.
