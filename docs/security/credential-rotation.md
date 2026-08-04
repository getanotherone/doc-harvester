# Credential rotation checklist

This is an owner-operated gate. Do not put credential values, screenshots containing them,
private URLs, database connection strings, or organization IDs in Git or tickets.

For every applicable integration—Yandex Disk, Yandex Wiki, Yandex Search/API, database,
object storage, Notion, Confluence, and deployment/CI secrets:

1. Identify its owner, scope, storage location, and consumers.
2. Create a least-privilege replacement credential.
3. Update local `.env` files and hosted secret stores without committing them.
4. Run a sanitized read-only smoke test, then any explicitly approved write test.
5. Revoke the old credential.
6. Prove the new credential works and the old credential no longer works.
7. Record only: credential label, owner, rotation date, verification date, old-value revoked
   (`yes/no`), and reviewer.

If a previously public credential cannot be proven revoked or rendered unusable by a
documented retirement control, Phase 1 remains incomplete even when secret scanning passes.

## Retirement alternative

When an integration is permanently abandoned, the owner may record an explicit retirement
disposition instead of creating a replacement credential. The record must identify the
control that makes old access unusable (for example, a blocked or deleted provider account)
and state that reactivation requires newly created credentials. Do not record account IDs,
old credential values, private URLs, or screenshots containing them.
