# Live deployment

Deployed and verified on 2026-09-07.

| Item | Value |
| --- | --- |
| Application | https://d1avnc6xl566f.cloudfront.net |
| AWS account | `201964534042` |
| Profile / region | `rama` / `us-east-1` |
| CloudFormation stack | `jso-candidate-library` |
| CloudFront distribution | `E39UM5HZQKXQJH` |
| VPC origin | `vo_C6IRyFyuqDBEd3plQJ0NXp` |
| EC2 instance | `i-07b2be6a7630989cb` |
| Existing user pool | `us-east-1_7lXAB7FYk` |
| Dedicated app client | `5a962m3bb7lld0j5chca56ctp0` |
| Reviewer group | `candidate-profile-reviewers` |
| Configured administrator | `jso_admin@org.in` |
| NeetoForm config secret | `jso-candidate-library/neetoform` |
| ECR image tag | `201964534042.dkr.ecr.us-east-1.amazonaws.com/jso-candidate-library:build-20260907191930` |
| Image digest | `sha256:05f7d0792d79d09e6d23bec477234f07ca66b27b72db4e37620413b9659b1a4b` |

The administrator was created with the requested permanent password and group access. No invitation was sent. The password is not stored in these files.

Verification completed:

- 31 automated backend tests and one separate desktop/mobile browser test passed.
- CloudFormation template passed cfn-lint and AWS validation; stack creation completed.
- EC2 container health passed through Systems Manager.
- Live CloudFront sign-in succeeded with the configured administrator.
- Live anonymous profile access was denied, authenticated access succeeded, another browser could not read cached profile data, and a revoked session cookie was rejected after logout.

**Import status: 0 candidates.** The NeetoForm API key and real attachment/field mappings have not been provided or verified. The known workspace `jso` and form `4c47b1a6-144c-44ea-a6ce-0a151cdcb630` are configured. Add the key and actual field/attachment settings to the NeetoForm secret before syncing.

To update the private configuration after editing `data/neeto-config.json` locally:

```bash
aws secretsmanager put-secret-value \
  --secret-id jso-candidate-library/neetoform \
  --secret-string file://data/neeto-config.json \
  --profile rama --region us-east-1 --query VersionId
aws ssm start-session --target i-07b2be6a7630989cb --profile rama --region us-east-1
```

Inside the Systems Manager session, run `sudo /opt/candidate-library/start.sh`. It preserves the profile data, rereads the secret, and restarts the application. Then sign in and click **Sync NeetoForm**.

The deployed stack is billable while running, including its NAT gateway and EC2 instance. See README.md for backups, updates, retention, and cleanup considerations.
