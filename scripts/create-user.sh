#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
username="${1:?Usage: ./scripts/create-user.sh admin@example.com}"
pool=$(terraform -chdir=infrastructure/terraform output -raw cognito_user_pool_id)
region=$(terraform -chdir=infrastructure/terraform output -raw aws_region)
group=$(terraform -chdir=infrastructure/terraform output -raw required_group)
if ! aws cognito-idp admin-get-user --user-pool-id "$pool" --username "$username" --region "$region" --query Username --output text >/dev/null 2>&1; then
  aws cognito-idp admin-create-user --user-pool-id "$pool" --username "$username" --user-attributes "Name=email,Value=$username" --message-action SUPPRESS --region "$region" --query User.Username --output text
fi
if [[ -n "$group" ]]; then
  aws cognito-idp admin-add-user-to-group --user-pool-id "$pool" --username "$username" --group-name "$group" --region "$region"
fi
# A hidden prompt keeps the permanent password out of shell history/process args.
.venv/bin/python scripts/set-user-password.py "$pool" "$username" "$region"
