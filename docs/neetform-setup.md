# NeetoForm setup

## API access

Official API documentation: [List submissions](https://apidocs.neetoform.com/api-reference/submissions/list-submissions).

For the supplied form configure:

```hcl
neetform_api_base_url = "https://jso.neetoform.com/api/external/v1"
neetform_form_id      = "4c47b1a6-144c-44ea-a6ce-0a151cdcb630"
```

The client calls `GET /forms/{form_id}/submissions`, authenticates with `X-Api-Key`, and paginates using `page_number` and `page_size`. It reads `submissions` and `total_count`. An API key with access to this workspace/form is required; a Neeto browser login is not an API key. Obtain the key through your account's API settings or administrator. This repository does not scrape the admin submissions page or store a Neeto login password.

Run `AWS_PROFILE=rama .venv/bin/python scripts/configure-secrets.py`. Enter the API key at the hidden prompt. The generated JSON secret contains `NEETO_API_KEY` and `NEETO_WEBHOOK_SECRET`; no values enter Terraform state or command arguments. AWS Secrets Manager's console can display the webhook secret for copying into Neeto. If no actual API key has been supplied, historical synchronization cannot be verified against your account.

## Webhook

1. In the form's webhook/integration settings, add a webhook for submission events.
2. Copy the exact URL from `terraform -chdir=infrastructure/terraform output -raw webhook_url`: `https://<api-domain>/webhooks/neetform`.
3. Set the signing secret to the same `NEETO_WEBHOOK_SECRET` saved in Secrets Manager.
4. Enable the webhook and submit a fictional test profile.
5. Confirm a 202 response, then check the authenticated profile library and CloudWatch status events.

Neeto sends `x-neeto-webhook-signature: sha256=<hex digest>`. The application computes HMAC-SHA256 over the original HTTP body bytes and compares in constant time before JSON parsing. See [Neeto request validation](https://help.neetoform.com/articles/validating-requests). Do not rewrite, pretty-print, or escape JSON before calculating its signature.

## Field and file mapping

See the [official sample webhook](https://help.neetoform.com/articles/sample-payload-for-webhook). It uses a `webhook` envelope with `id`, `submitted_at`, and `answers`. Answers are keyed by field code and contain `field`, `value`, and `type`. Neeto's field advanced properties identify these codes. The API may instead supply `responses` with label/slug/value. Both are supported, along with common flat and nested fixtures.

Map actual field codes or labels to internal meanings:

```hcl
neeto_field_mapping = {
  name     = "name"
  email    = "email"
  linkedin = "linkedin"
  support  = "I'm willing to support this casue by"
  theme    = "theme"
  file     = "file_upload"
}
neeto_attachment_hosts = ["EXACT-HOST-FROM-YOUR-ATTACHMENT-URL"]
```

Replace every placeholder with observed values. Prefer stable field codes if labels change. Equivalent backend settings are `NEETO_FIELD_NAME`, `NEETO_FIELD_EMAIL`, `NEETO_FIELD_LINKEDIN`, `NEETO_FIELD_SUPPORT`, `NEETO_FIELD_THEME`, and `NEETO_FIELD_FILE`.

Attachment hosts are an explicit exact-match allowlist, including every legitimate redirect destination. Empty configuration intentionally refuses downloads. Inspect a submission privately in Neeto or a local redacted fixture to identify hosts; do not log full signed URLs. HTTPS is required, and private/link-local DNS addresses are rejected. Avoid wildcard hosts. Files may be URL strings, `{name,url}` objects, arrays, or JSON-encoded values. Update `backend/src/services/neetform_parser.py` if your account uses another shape. Only the first PDF is imported in V1.

Redeploy Terraform after changing mappings or hosts. Then use **Sync Now** to recover earlier partial imports. A failed file transfer retains profile metadata. Submission ID and submission date are required; if your payload uses a different envelope, adapt the isolated mapper and add a redacted test fixture.

## Manual verification

With a backend running locally:

```bash
./scripts/test-webhook.sh
./scripts/test-invalid-webhook.sh
```

For a deployed endpoint pass its URL as the first shell-script argument and an optional fixture path as the second. Provide the actual secret through a secure local environment. Never paste the secret into a command that will be committed or logged. Repeat a valid delivery and confirm one profile, not two. A 202 only confirms acceptance: check eventual worker status as well.

## Verified attachment hosts and recovery

On 8 September 2026, the supplied form's attachment links used `app.neetoform.com`, which redirected to `neeto-form-production-v3.s3.amazonaws.com`. Both exact hosts are now allowed in the live deployment and configuration examples. No wildcard host allowance is needed. If a future Neeto storage change introduces another host, verify it before extending the allowlist.

After changing hosts, apply Terraform and run **Sync Now** to retry failed downloads. The recovery synchronized 52 submissions and stored 32 PDFs. The remaining 20 first attachments were 14 Word documents, 5 JPEGs, and 1 PNG. Their profile metadata is retained, but this PDF-only version rejects those document formats. They need PDF versions to be displayed by the current application.

The supplied form's Support column is spelled **“I'm willing to support this casue by”** (including `casue`). Its API slug is `type-a-question`; the mapping uses the exact label to avoid relying on a generic slug. Selected answers arrive as a list and are joined into the full Support text shown in the library. On 8 September 2026, this column contained answers on 26 of the 52 submissions; submissions without an answer are left blank.


### Theme custom column

Neeto internal custom columns arrive in `field_values` rather than `responses`.
Configure `neeto_field_mapping.theme` (or local `NEETO_FIELD_THEME`) with the
column's `field_id`. The importer reads its `data.value`; do not use the individual
answer's `id`, which differs between submissions. For the deployed JSO form the
Theme field ID is `00abe109-f74b-4a70-9f50-fe79b1a14fff`.
After changing the mapping, deploy and click **Sync Now** to refresh existing
profiles. Theme values appear on profile cards, details, and in the theme filter.
Missing or blank values continue to display **Other**. Custom-column edits can
be refreshed using Sync Now even if Neeto does not send a submission webhook for
those edits.
