#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
echo 'Data protection intentionally blocks destruction of profile storage and managed user pools.'
echo 'Follow docs/deployment.md to back up or explicitly retain those resources before proceeding.'
read -r -p 'Type DESTROY to generate a destroy plan: ' answer
[[ "$answer" == 'DESTROY' ]] || exit 1
terraform -chdir=infrastructure/terraform plan -destroy -out=../../.build/destroy.tfplan
terraform -chdir=infrastructure/terraform apply ../../.build/destroy.tfplan
