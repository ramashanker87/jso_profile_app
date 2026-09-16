#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
tf=(terraform -chdir=infrastructure/terraform)
export AWS_REGION="$("${tf[@]}" output -raw aws_region)"
export VITE_API_BASE_URL="$("${tf[@]}" output -raw api_url)"
export VITE_COGNITO_USER_POOL_ID="$("${tf[@]}" output -raw cognito_user_pool_id)"
export VITE_COGNITO_CLIENT_ID="$("${tf[@]}" output -raw cognito_client_id)"
export VITE_COGNITO_REGION="$AWS_REGION"
export VITE_COGNITO_OAUTH_DOMAIN="$("${tf[@]}" output -raw cognito_oauth_domain)"
export VITE_GOOGLE_LOGIN_ENABLED="$("${tf[@]}" output -raw google_login_enabled)"
export VITE_COGNITO_REQUIRED_GROUP="$("${tf[@]}" output -raw required_group)"
export VITE_USE_MOCK_API=false
export VITE_USE_LOCAL_API=false
(cd frontend && npm run build)
bucket=$("${tf[@]}" output -raw frontend_bucket_name)
distribution=$("${tf[@]}" output -raw cloudfront_distribution_id)
# Upload hashed assets first; index.html is the final switch. Do not delete old
# assets immediately, so browsers with the previous HTML keep working.
aws s3 sync frontend/dist/ "s3://$bucket/" --exclude index.html --exclude sample-profile.pdf --cache-control 'public,max-age=31536000,immutable' --only-show-errors
aws s3 cp frontend/dist/index.html "s3://$bucket/index.html" --cache-control 'no-cache,no-store,must-revalidate' --content-type text/html --only-show-errors
aws cloudfront create-invalidation --distribution-id "$distribution" --paths / /index.html /login /signup '/profiles/*' /members '/members/*' --query Invalidation.Id --output text
"${tf[@]}" output
