# S3-compatible test connection

This guide starts with local storage and then uses a small Cloudflare R2 Standard bucket.
R2 exposes an S3-compatible API and currently includes monthly free storage/operation usage,
but it requires activating an R2 subscription. It is a real billed service, not an isolated
sandbox, so keep usage tiny and review the provider dashboard.

Official references:

- [R2 pricing and monthly free usage](https://developers.cloudflare.com/r2/pricing/)
- [Create a bucket and use the S3 API](https://developers.cloudflare.com/r2/get-started/s3/)
- [Create bucket-scoped R2 credentials](https://developers.cloudflare.com/r2/api/tokens/)

## 1. Verify the workflow locally

From the repository with the virtual environment active:

```bash
python -m pip install -e '.[s3]'
doc-harvester source discover manual README.md \
  --output /tmp/doc-harvester-s3-manifest.json
doc-harvester source process /tmp/doc-harvester-s3-manifest.json \
  --root . --output /tmp/doc-harvester-s3-dataset
doc-harvester source store /tmp/doc-harvester-s3-dataset \
  --storage local --local-root /tmp/doc-harvester-storage \
  --destination manual-test/run-001
```

Confirm the last command reports provider `local` and four uploaded files. Repeating the
same command without `--overwrite` should fail safely because the destination exists.

## 2. Create a small R2 bucket

1. Sign in to Cloudflare.
2. Open **Storage & databases → R2 → Overview**.
3. Activate the R2 subscription if required; read the displayed billing terms.
4. Create a bucket such as `doc-harvester-test` using **Standard** storage.
5. Do not enable public access; the test uses authenticated S3 calls only.

## 3. Create least-privilege credentials

1. On **R2 → Overview**, select **Manage** beside API Tokens.
2. Create a user or account token with **Object Read & Write**.
3. Scope it to the single `doc-harvester-test` bucket.
4. Copy the Access Key ID and Secret Access Key immediately; the secret is shown once.
5. Copy the S3 endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.

Do not paste these values into Git, a task summary, screenshots, or shell command history.

## 4. Put the settings in the ignored `.env`

Create the file if needed, then open it in TextEdit on macOS:

```bash
touch .env
open -e .env
```

Add these values, replacing only the placeholders:

```dotenv
DOC_HARVESTER_STORAGE=s3
DOC_HARVESTER_S3_BUCKET=doc-harvester-test
DOC_HARVESTER_S3_PREFIX=doc-harvester-test
DOC_HARVESTER_S3_ENDPOINT_URL=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
DOC_HARVESTER_S3_REGION=auto
AWS_ACCESS_KEY_ID=<ACCESS_KEY_ID>
AWS_SECRET_ACCESS_KEY=<SECRET_ACCESS_KEY>
AWS_SESSION_TOKEN=
```

The CLI does not automatically read `.env`. Export it into the current shell:

```bash
set -a
source .env
set +a
```

## 5. Store the tiny reviewed dataset

Use a new destination suffix each time:

```bash
doc-harvester source store /tmp/doc-harvester-s3-dataset \
  --storage s3 --destination manual-test/run-001
```

Expected result: provider `s3`, the explicit destination, and four uploaded files. In the R2
dashboard, the objects appear below
`doc-harvester-test/manual-test/run-001/`. Repeating the command without `--overwrite` should
return non-zero and preserve the existing objects.

## 6. Cleanup and revoke

1. Delete only the `doc-harvester-test/manual-test/run-001/` objects in the R2 dashboard.
2. Delete the bucket if it is no longer needed.
3. Revoke the test API token.
4. Remove the credential values from `.env`, then clear them from the shell or close it.
5. Review R2 usage/billing to confirm the test remained within the intended limits.

If a remote upload fails after writing some objects, inspect and remove that exact prefix
before retrying with a new destination. Remote multi-object uploads are not atomic.
