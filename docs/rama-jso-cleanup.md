# Old JSO deployment cleanup in rama

Scope authorized on 12 September 2026: remove only the old JSO application in
AWS account `201964534042`, profile `rama`, region `us-east-1`.
The active JSO deployment in profile `jso` (account `223885744552`) is separate.

The reviewed Terraform destruction plan contains 44 managed resources: the old
JSO API and routes, two Lambda functions, three DynamoDB tables, two S3 buckets,
CloudFront distribution and supporting configuration, IAM roles/policies, logs,
Neetoform secret, and the JSO Cognito client and access group.

The shared Cognito pool `us-east-1_7lXAB7FYk` belongs to
`student-readability-pilot-users`; the pool and users are preserved, along with
all student-readability infrastructure. Only the JSO client
`29v92ecqm5ssc9f2cpgbkin9kr` and group `profile-library-users` are removed.

Cleanup uses an isolated configuration under ignored `.build/rama-cleanup`,
with an explicit provider account allowlist for rama and a pre-cleanup state
backup. Deletion guards were relaxed only in this copy; production JSO guards
remain intact. The two old buckets were emptied (157 document object versions
and 20 frontend object versions) and table deletion protection was disabled
only for the old rama tables. The Neetoform secret uses its configured
30-day recovery window.

Do not apply the default workspace to recreate this retired deployment. Future
JSO deployments use `AWS_PROFILE=jso TF_WORKSPACE=jso` and `jso.tfvars`.

## Legacy stack discovered during cleanup

The earlier `jso-candidate-library` stack retirement had failed while waiting
for CloudFront. Ownership was confirmed through CloudFormation's resource list.
Cleanup was retried for this JSO-only stack, including its second CloudFront
distribution, private origin, EC2 server, VPC, NAT gateway, public IP, IAM role,
origin secret and separate Cognito app client. The shared Cognito pool is not a
stack resource. The server's retained 30-GB disk was changed to delete on
termination. The external `jso-candidate-library` ECR repository and all its
images were deleted; `jso-candidate-library/neetoform` was scheduled for deletion
with a 30-day recovery window.

The 44 Terraform resources have been verified absent and the default rama state
updated to reflect that destruction. No matching DynamoDB backups were returned
by the backup inventory, and no profile-library-tagged resources were found in
the original default region eu-north-1. The active jso website returned HTTP 200.

## Final verification

Both JSO deployments are removed. CloudFormation no longer finds the legacy
stack. Direct AWS checks confirmed the legacy server terminated and its disk,
VPC, NAT gateway, public IP, images, CloudFront distributions, IAM role and JSO
app clients are gone. The student application CloudFront distribution and
shared Cognito pool remain. The two external Neetoform secrets are pending
their configured 30-day deletion recovery windows; their values were not read.
