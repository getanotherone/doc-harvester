# P1 — Sanitize

## Summary

Phase 1 makes the public snapshot safe to distribute and installs controls that prevent
credentials, private URLs, generated data, and personal paths from returning. Phase 1 was
completed on 2026-08-04 after an owner-approved credential inventory and disposition review.

## Background

The highest-risk blocker was generated `datasets/` content in Git history. The public
repository now starts from a small sanitized snapshot; automated full-history scanning and
runtime URL redaction make that state repeatable rather than relying on a one-time cleanup.

## User story / use case

As an open-source maintainer, I can publish and accept contributions without disclosing
credentials, private source material, organization identifiers, or workstation details.

## System constraints

- Real `.env` files, runtime reports, local maps, datasets, chunks, logs, state, and wiki
  exports are not public artifacts.
- Secrets must be revoked even if removed from Git; deletion does not invalidate them.
- Downloaded documents require a separate redistribution decision from the source-code
  license.
- Logs may retain URL scheme, host, and path, but never userinfo, query parameters, or
  fragments.

## Functional requirements

- `P1-FR-01`: Rotate and revoke all previously used credentials.
- `P1-FR-02`: Scan all Git history and the non-ignored working tree with Gitleaks.
- `P1-FR-03`: Exclude generated/private artifacts from Git.
- `P1-FR-04`: Record redistribution decisions for downloaded documents.
- `P1-FR-05`: Redact authentication URL data from runtime logs.
- `P1-FR-06`: Remove personal paths, organization IDs, and private Wiki URLs.
- `P1-FR-07`: Ignore `.env` and provide a placeholder-only `.env.example`.
- `P1-FR-08`: Build the public repository from a clean sanitized snapshot.

## API requirements

No public API shape changes. Security helpers sanitize only console/log representations;
the original URL remains available to the network request and manifest logic.

## Non-functional requirements

- Secret scanning runs on every push and pull request with complete Git history.
- Findings are redacted and scan artifacts are not uploaded by CI.
- Security controls have unit tests and work without network access.

## Logging and monitoring

CI is the enforcement point for committed history. Maintainers run
`scripts/scan_secrets.sh` before publication and retain only a sanitized pass/fail record.

## Edge cases

- Request libraries can repeat a sensitive URL inside exception text.
- URL credentials (`user:password@host`) must be removed as well as query strings.
- Ignored `.env`, maps, and reports intentionally remain outside the public-tree scan.
- A scan passing does not prove that an old credential was rotated.

## Acceptance criteria

- Full-history and public working-tree scans pass.
- CI performs a full-history Gitleaks scan.
- URL sanitizer tests prove credentials, queries, and fragments do not reach logs.
- No generated documents or private identifiers are reachable from public refs.
- Credential rotation and redistribution review are recorded using the security runbook.

## Current evidence (updated 2026-08-04)

| Requirement | Status | Evidence |
|---|---|---|
| Generated data removed from current history | Passed | No dataset/document artifact paths are reachable from fetched public refs. |
| Ignore rules and safe example | Passed | `.gitignore` excludes local secrets/artifacts; `.env.example` contains placeholders. |
| Personal path removal | Passed | Public documentation uses repository-relative paths. |
| URL log redaction | Passed | Security tests are included in the 81-test standalone run, repeated on 2026-08-04. |
| Repeatable secret scan | Passed locally; CI configured | Gitleaks found no leaks in complete history or the non-ignored working tree on 2026-08-04. |
| Credential rotation/revocation | Passed by disposition review | Yandex is retired with a blocked account; the new Notion test token is retained; other provider credentials are not configured. |
| Redistribution decision | Documented for current snapshot | See `docs/security/redistribution-review.md`. |

## Sanitized credential evidence (2026-08-04)

Only environment-variable names and `set`/`empty` state were inspected. No credential value,
token fingerprint, private URL, account identifier, or organization identifier was printed
or committed.

| Integration | Disposition | Local configuration evidence |
|---|---|---|
| Yandex Disk, Wiki, and Search | Retired; owner reports the Yandex account is blocked and the integrations will not be used again | Credential variables are empty |
| Notion | Active; newly created least-scope token used for the Notion validation and approved to remain | `NOTION_TOKEN` is set; value not inspected or recorded |
| Confluence | Not configured | Credential and destination variables are empty |
| S3/AWS object storage | Not configured | Credential, bucket, endpoint, and region variables are empty |
| Database | No external database credential configured for this repository | Owner confirmation; no credential recorded |
| Custom CI/deployment credentials | Not configured | Owner confirmation; workflow uses only GitHub's job-scoped token |
| Local HTTP API | Not configured for production use | `SCRAPPER_API_KEY` contains only the documented placeholder |

The owner accepted account blocking plus permanent retirement as the Yandex credential
disposition. Re-enabling any Yandex integration requires creation of new credentials rather
than reuse of historical ones.
