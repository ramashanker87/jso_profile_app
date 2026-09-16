#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for program in aws terraform npm python3; do command -v "$program" >/dev/null || { echo "Missing prerequisite: $program" >&2; exit 1; }; done
if [[ ! -f infrastructure/terraform/terraform.tfvars ]]; then
  echo 'Copy infrastructure/terraform/terraform.tfvars.example to terraform.tfvars and review the settings first.' >&2
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --index-url "${PACKAGE_INDEX_URL:-https://pypi.org/simple}" -r backend/requirements-dev.txt
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
(cd frontend && npm ci && npm test && npm run build)
./scripts/build-backend.sh
terraform -chdir=infrastructure/terraform init -input=false
terraform -chdir=infrastructure/terraform validate
terraform -chdir=infrastructure/terraform plan -input=false -out=../../.build/serverless.tfplan
# terraform plan's path above is relative to its working directory.
terraform -chdir=infrastructure/terraform apply ../../.build/serverless.tfplan
./scripts/deploy-frontend.sh
printf '\nSet integration secrets with .venv/bin/python scripts/configure-secrets.py before enabling NeetoForm webhooks.\n'
