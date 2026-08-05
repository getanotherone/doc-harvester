# AWS S3 Free Plan test connection

This guide uses AWS Free Plan to learn the account, billing, IAM, S3, and SDK workflow while
storing one tiny reviewed doc-harvester dataset. It was last verified against official AWS
documentation on 2026-08-05. AWS terms and console labels can change, so review the linked
official pages during signup.

Official references:

- [Current AWS Free Tier and Free Plan FAQ](https://aws.amazon.com/free/free-tier-faqs/)
- [AWS cost-control tutorial](https://docs.aws.amazon.com/hands-on/latest/control-your-costs-free-tier-budgets/control-your-costs-free-tier-budgets.html)
- [Root-user security practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html)
- [Create a general-purpose S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/create-bucket-overview.html)
- [IAM policy examples for one S3 bucket](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_examples_s3_rw-bucket-console.html)

## Important Free Plan lifecycle

For an eligible new customer, choose **Free Plan** during signup:

- The plan ends at the earlier of six months after account creation or exhaustion of Free
  Tier credits.
- AWS requires a payment method but states that it is not charged unless the account is
  upgraded to Paid Plan.
- At expiry, AWS closes the Free Plan account and retains its data for 90 days. Restoring or
  downloading that data during the retention period requires upgrading to Paid Plan.
- Creating or joining an AWS Organization, or configuring AWS Control Tower, automatically
  upgrades the account and causes the remaining Free Tier credits to expire.
- Remaining credits can continue after an intentional Paid Plan upgrade, but expire 12 months
  after account creation unless invalidated by an Organization or Control Tower action.

This is not a disposable sandbox. Keep the workload private and tiny, monitor usage, and clean
up all resources before the plan ends.

## 1. Create and secure the AWS account

1. Create a new AWS account and explicitly select **Free Plan**.
2. Save the account creation date and the displayed plan/credit expiry dates.
3. Sign in as the root user only for initial account administration.
4. Open the root account security settings and register MFA.
5. Confirm the root user has no access keys. Never create root access keys for this test.
6. Do not configure AWS Organizations or Control Tower during the Free Plan experiment.

## 2. Configure cost visibility before resources

1. Open **Billing and Cost Management**.
2. Review the **Cost and Usage** widget and current Free Tier credit balance.
3. From the console's **Explore AWS → Earn AWS credits** workflow, choose the guided
   **Set up a cost budget using AWS Budgets** activity when available.
4. Create the suggested monthly cost budget and supply an email address you monitor.
5. Confirm the alert email and record the budget name in your private learning notes.

AWS states that Free Plan accounts receive credit/expiry notifications, but a budget provides
hands-on FinOps practice and a second signal. Billing data can arrive after resource activity,
so do not treat a currently empty dashboard as proof that a resource is free.

## 3. Choose one region

Use one region consistently for the bucket, environment, console, and cleanup. This guide uses
`ap-southeast-1` as a straightforward example for Southeast Asia. For a real project, region
selection should consider service availability, data residency, latency, and regional pricing.

## 4. Create a private test bucket

Open **Amazon S3 → Buckets → Create bucket** and use:

| Setting | Test value |
|---|---|
| Bucket type | General purpose |
| Bucket name | A globally unique name such as `doc-harvester-test-<random-suffix>` |
| Region | `ap-southeast-1` |
| Object ownership | Bucket owner enforced; ACLs disabled |
| Block Public Access | Keep all four settings enabled |
| Versioning | Disabled for this disposable test |
| Default encryption | SSE-S3 |
| Object Lock | Disabled |

Do not use an email address, customer name, or confidential identifier in the bucket name.
Optionally add tags such as `Project=doc-harvester` and `Environment=test` for cost-allocation
practice. Do not upload anything through the console yet.

## 5. Create a least-privilege IAM policy

The application needs `PutObject` to upload and `GetObject` for its safe conflict preflight.
It also needs `ListBucket` on this one dedicated test bucket: without it, AWS can return `403`
instead of `404` when `HeadObject` checks a key that does not exist. It does not need permission
to create/delete buckets, change public access, or list every bucket. In
**IAM → Policies → Create policy → JSON**, use the following policy after replacing both bucket
placeholders with the exact bucket name:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListDedicatedTestBucket",
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<BUCKET_NAME>"
    },
    {
      "Sid": "StoreReviewedDocHarvesterDatasets",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::<BUCKET_NAME>/doc-harvester-test/*"
    }
  ]
}
```

Name it `DocHarvesterTestObjectAccess`. This policy intentionally cannot delete objects;
cleanup remains a deliberate console action by the account administrator.

## 6. Create a test IAM identity and access key

For this short local compatibility test:

1. Open **IAM → Users → Create user**.
2. Name the user `doc-harvester-test`.
3. Do not enable AWS Management Console access for the user.
4. Attach only `DocHarvesterTestObjectAccess`.
5. Open the user's **Security credentials** tab and create one access key for an application
   running outside AWS.
6. Save the Access Key ID and Secret Access Key in the ignored local `.env` immediately. The
   secret cannot be retrieved again.

AWS recommends temporary credentials where possible. A narrowly scoped IAM-user key is used
here only to make the first local S3 compatibility test understandable. Revoke it immediately
after testing; a later exercise can replace it with temporary `aws login` or role credentials.

Never create or use a root-user access key. Never paste a credential into Git, a task, a
screenshot, documentation, or a shell command.

## 7. Configure doc-harvester locally

Activate the virtual environment and install the optional S3 adapter:

```bash
source .venv/bin/activate
python -m pip install -e '.[s3]'
```

Create the ignored environment file if needed, then open it in TextEdit on macOS:

```bash
touch .env
open -e .env
```

Add these values, replacing the placeholders. The endpoint stays blank for AWS S3:

```dotenv
DOC_HARVESTER_STORAGE=s3
DOC_HARVESTER_S3_BUCKET=<BUCKET_NAME>
DOC_HARVESTER_S3_PREFIX=doc-harvester-test
DOC_HARVESTER_S3_ENDPOINT_URL=
DOC_HARVESTER_S3_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=<IAM_ACCESS_KEY_ID>
AWS_SECRET_ACCESS_KEY=<IAM_SECRET_ACCESS_KEY>
AWS_SESSION_TOKEN=
```

The CLI does not automatically load `.env`. Export it into the current terminal:

```bash
set -a
source .env
set +a
```

Do not print the environment or run commands that echo credential values. If the AWS CLI is
already installed, `aws sts get-caller-identity` is a safe identity check because it does not
display the secret key.

## 8. Build and store a tiny reviewed dataset

Use a new numeric suffix if any `/tmp` path already exists:

```bash
doc-harvester source discover manual README.md \
  --output /tmp/doc-harvester-aws-manifest-001.json

doc-harvester source process /tmp/doc-harvester-aws-manifest-001.json \
  --root . \
  --output /tmp/doc-harvester-aws-dataset-001

doc-harvester source store /tmp/doc-harvester-aws-dataset-001 \
  --storage s3 \
  --destination manual-test/run-001
```

Expected storage result:

- provider is `s3`;
- destination is `manual-test/run-001`;
- four files are uploaded for this one-document dataset;
- objects appear under
  `doc-harvester-test/manual-test/run-001/` inside the configured bucket.

Repeat the final command once without `--overwrite`. It should fail safely because all target
objects are preflighted and existing objects are protected by default.

## 9. Verify and record privacy-safe evidence

In the S3 console:

1. Confirm the bucket still says **Objects can be public: No** or equivalent.
2. Confirm exactly the expected processing report, document, chunks, and quality artifacts.
3. Review bucket properties, permissions, region, encryption, and tags.
4. Review the Billing/Free Tier/credits dashboards after AWS usage data updates.

Record only the region, object count, command status, and redacted screenshots. Do not publish
the account ID, full bucket name, IAM ARN, access key ID, object contents, or billing identity.

## 10. Cleanup and credential revocation

1. Delete the `doc-harvester-test/manual-test/run-001/` objects in the S3 console.
2. Delete the bucket if no further exercise needs it.
3. In IAM, deactivate and then delete the test user's access key.
4. Delete the `doc-harvester-test` user and the custom policy if they are no longer needed.
5. Remove the AWS credential values from `.env` and close the terminal to clear exported values.
6. Review all regions and the billing dashboard for unexpected resources or usage.

Before Free Plan expiry, export anything you want to retain and remove every test resource.
If you remain on Free Plan, AWS closes the account at expiry. If you intentionally upgraded to
Paid Plan, follow the AWS account-closure process after resource cleanup to prevent future use.

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| `AccessDenied` during preflight | Missing `s3:GetObject`/`s3:ListBucket` or wrong ARN | Both dedicated bucket and object-prefix policy statements |
| `AccessDenied` during upload | Missing `s3:PutObject` | IAM policy action and exact object ARN |
| `NoSuchBucket` | Bucket name or selected account is wrong | `DOC_HARVESTER_S3_BUCKET` and console account |
| Redirect or region error | Bucket and configured regions differ | Set `DOC_HARVESTER_S3_REGION` to the bucket region |
| Existing destination error | Safe default found prior objects | Use a new `run-NNN`; overwrite only intentionally |
| `InvalidAccessKeyId` | Wrong/deleted key or stale exported environment | Reopen the IAM user and reload the correct ignored `.env` |
| `ExpiredToken` | Temporary credentials expired | Refresh credentials and reload all three AWS credential fields |

If a remote upload fails after writing some objects, inspect and remove that exact prefix before
retrying with a new destination. S3 multi-object uploads are not atomic.
