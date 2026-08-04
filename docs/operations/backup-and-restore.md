# Backup and restore runbook

Backups are complete only after a restore check. Store all outputs in encrypted storage
outside this repository, and never paste tokens or private download URLs into evidence.

## Repository

1. Choose a dated directory on independent storage and create a complete bundle:

   ```bash
   git bundle create /path/to/external-backup/doc-harvester.bundle --all
   git bundle verify /path/to/external-backup/doc-harvester.bundle
   ```

2. Preserve in-progress non-secret work separately:

   ```bash
   git status --short
   git diff --binary > /path/to/external-backup/working-tree.patch
   ```

   Review untracked files manually. Copy only required files; never copy `.env`, local
   publish maps, reports, browser state, datasets, or credentials into a shared backup.

3. Restore-test the bundle in a temporary directory:

   ```bash
   git clone /path/to/external-backup/doc-harvester.bundle /tmp/doc-harvester-restore-test
   git -C /tmp/doc-harvester-restore-test log -1 --oneline
   ```

## Retired source data

The owner confirmed on 2026-07-16 that the historical Yandex Disk data is retired and will
never be used again. It is therefore outside the recovery scope and does not require a P0
backup. This is an intentional retention decision, not an unverified backup claim.

Do not delete or alter Yandex Disk data as part of this decision.

## Sanitized evidence record

Record enough information to demonstrate recovery without publishing sensitive details:

```text
Date: YYYY-MM-DD
Operator: repository maintainer
Backup type: Git bundle
Backup storage: encrypted external/local backup storage (no personal path)
Backed-up commit: <short commit ID>
git bundle verify: passed
Restore clone: passed
Restored HEAD: <short commit ID>
Secrets/private URLs included in evidence: no
```

The exact filesystem path, device serial number, account name, tokens, private URLs, and
contents of local `.env` files are not evidence and must not be recorded publicly.
