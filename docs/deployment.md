# Deployment and operations

## First deployment

```bash
export AWS_PROFILE=rama
aws sts get-caller-identity --profile rama --region us-east-1
make setup
cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
# Review/edit terraform.tfvars before running deployment.
./scripts/deploy.sh
.venv/bin/python scripts/configure-secrets.py
./scripts/create-user.sh admin@example.com
```

Defaults create a new administrator-only Cognito pool in eu-north-1. To reuse the supplied account's pool, set `aws_region = "us-east-1"`, `existing_cognito_user_pool_id = "us-east-1_7lXAB7FYk"`, and `required_group = "profile-library-users"`. A separate public SPA client and access group are created without changing other applications' clients. Existing users can be added to the group; sign out and back in afterward. Do not migrate the region of an existing user pool.

Deployment builds a Python 3.12 ZIP, runs backend/frontend tests, creates a saved Terraform plan, applies it, builds the UI with real output values, uploads hashed assets before index.html, and invalidates CloudFront. Terraform manages Lambda deployment directly. The generated CloudFront URL works without a domain. For a custom domain configure an existing us-east-1 ACM certificate and create the DNS alias yourself; Route53 is optional.

Outputs include `frontend_url`, `cloudfront_url`, `api_url`, `cognito_user_pool_id`, `cognito_client_id`, `profile_bucket_name`, `dynamodb_table_name`, and `webhook_url`. Additional operational outputs expose IDs and the secret ARN, never secret values.

To deploy only frontend changes: `./scripts/deploy-frontend.sh`. To review infrastructure without applying: build the backend, then run Terraform init, validate, and plan. Environment changes are applied through Terraform, not manual Lambda edits.

## Verification

Sign in, verify API list/detail, submit a signed fictional webhook, wait for the worker, repeat it, and check that only one profile exists. Check inline and attachment URLs, anonymous S3 denial, invalid-signature rejection, and CloudWatch events. Configure a real Neeto API key and field/host mapping before testing historical Sync Now. A successful mock integration does not establish access to the real Neeto account.

A full sync never deletes data. Failed documents are retried on subsequent submission/sync processing. Search scans the small profile table; monitor read charges and latency as the dataset grows. Optional Lambda error alarms can be enabled with `enable_error_alarms`; configure your notification destination separately if desired.

## Terraform state

Local state is initially used and ignored by Git. Back it up securely; losing it does not delete resources but makes management difficult. Do not run concurrent Terraform operations.

For a later remote backend, create a separate private, encrypted, versioned S3 state bucket with narrowly scoped IAM. Add a `backend "s3"` block with bucket/key/region and `use_lockfile = true` (Terraform 1.10+), then run `terraform init -migrate-state`. Review the migration and retain a protected backup. This needs no separate DynamoDB locking table. Do not store backend credentials in HCL.

## Removing resources

Deployment never runs destroy. `./scripts/destroy.sh` requires typing DESTROY, creates a destroy plan, and applies only that plan. It intentionally fails while retained data resources have `prevent_destroy` enabled. Before a full teardown:

1. Export/retain required DynamoDB data and PDFs, and confirm your retention decision.
2. Review references to `prevent_destroy` in S3, DynamoDB, and Cognito HCL. Remove protections only for resources you explicitly intend to delete; apply any required DynamoDB/Cognito deletion-protection change first.
3. Empty buckets only after deciding what data to retain. No script force-empties them.
4. Re-run the reviewed destroy plan. An existing external Cognito pool is never managed/deleted by this stack.

Alternatively move retained resources out of this Terraform state before destroying the remaining infrastructure, preserving ownership records for future maintenance. Secrets have a recovery window. These deliberate protections mean teardown is not a one-command deletion of personal data.

## Earlier EC2 deployment

The previous CloudFormation deployment is separate from this Terraform stack. Creating the new stack does not stop its EC2/NAT resources or migrate its local database automatically. Inspect and preserve any earlier data, verify the new site, then retire the legacy stack explicitly. Its details are in [legacy-deployment.md](legacy-deployment.md). Costs from that stack continue until it is retired.
