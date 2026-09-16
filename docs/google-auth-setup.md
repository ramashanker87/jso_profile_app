# Google signup and sign-in

The login page supports **Continue with Google** through Cognito's authorization
code flow with PKCE (handled by Amplify). First-time Google users receive a
Cognito account. They must join `profile-library-users` before the API grants
access; until then the UI displays **Awaiting approval**. Password login remains
available. This does not automatically link Google identities to existing
password accounts or grant access based on a matching email address.

## Google Cloud setup for jso

Create an OAuth client of type **Web application** in your Google Cloud project.
Configure its consent screen for JSO, selecting the intended audience and adding
test users if the project is in testing mode. Request only `openid`, `email` and
`profile`.

Authorized JavaScript origin:

```text
https://profile-library-prod-223885744552.auth.us-east-1.amazoncognito.com
```

Authorized redirect URI (exactly, with no trailing slash):

```text
https://profile-library-prod-223885744552.auth.us-east-1.amazoncognito.com/oauth2/idpresponse
```

Google redirects to Cognito; Cognito redirects to
`https://dse76eldn9xf5.cloudfront.net/login`.

See [AWS Google provider setup](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html)
and [Google OAuth setup](https://developers.google.com/identity/openid-connect/openid-connect).

## Store credentials and enable

In AWS Secrets Manager in account `223885744552`, region `us-east-1`, create a
secret (for example `profile-library-prod/google-oauth`) containing a JSON
object with key `client_secret` and the Google client secret as its value.
Do not put the secret into frontend environment variables or version control.
Terraform reads the value from Secrets Manager; sensitive values also appear
in local Terraform state and saved plan files, which must be kept private.

Add the following settings to the ignored local file
`infrastructure/terraform/jso.tfvars` (replace the example values):

```hcl
enable_google_login      = true
google_client_id         = "YOUR_CLIENT_ID.apps.googleusercontent.com"
google_oauth_secret_arn  = "ARN_OF_YOUR_GOOGLE_OAUTH_SECRET"
```

Then run:

```bash
export AWS_PROFILE=jso TF_WORKSPACE=jso
terraform -chdir=infrastructure/terraform plan -var-file=jso.tfvars -out=../../.build/jso-google.tfplan
terraform -chdir=infrastructure/terraform apply ../../.build/jso-google.tfplan
./scripts/deploy-frontend.sh
```

The button is shown only when Terraform output `google_login_enabled` is true.
Provisioning the domain alone does not enable Google sign-in. The client secret
is used by Cognito only; neither the frontend nor application Lambda needs it.

## Approve a new account

After a user signs in with Google for the first time or verifies their email
after email-and-password signup, locate that user's account in Cognito pool `us-east-1_RbUqJHia7` in the AWS console.
Verify the intended user, then add its Cognito username to the application group:

```bash
aws cognito-idp admin-add-user-to-group \
  --profile jso --region us-east-1 \
  --user-pool-id us-east-1_RbUqJHia7 \
  --username 'COGNITO_USERNAME' \
  --group-name profile-library-users
```

The user should sign out and sign in again to receive an updated access token.
The frontend approval screen complements server-side access checks; the API
continues to require the application group even if the browser is modified.

## Verification after credentials are enabled

Use a Google test account to complete the redirect flow, confirm the pending
approval screen, approve that account, then sign in again and verify Profiles
and Members. Test sign-out, cancelled Google login, and existing password login.
Google credentials are required for this end-to-end verification.

## Email and password signup

The signup page also accepts email, password and password confirmation. Cognito
self-registration is enabled, with email verification required. Passwords need
at least 12 characters including uppercase, lowercase, a number and a symbol.
The verification screen supports resending codes and resuming an unfinished
signup. After verification, users log in and see Awaiting approval until an
administrator adds them to `profile-library-users` as described above. Signup
and email confirmation do not grant that group or access to application data.
Google signup continues to use the same approval requirement.
