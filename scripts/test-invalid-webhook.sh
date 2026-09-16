#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python scripts/send-webhook.py "${1:-http://127.0.0.1:8000/webhooks/neetform}" "${2:-backend/tests/fixtures/webhook.json}" --invalid
