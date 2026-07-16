# Phase Documentation

Each significant implementation phase should leave enough public documentation for a
contributor to understand the problem, review the design, and reproduce its acceptance
tests without access to a maintainer's private services.

## Directory convention

```text
docs/phases/<phase-id>-<short-name>/
├── task-summary.md
└── manual-test-cases.md
```

Use a stable, domain-specific phase ID such as `PUB-001`; do not renumber existing phases.
Requirement and test IDs derive from it, for example `PUB-001-FR-01`, `PUB-001-AC-01`,
and `PUB-001-TC-01`.

Start from the reusable files:

- [Task summary template](templates/task-summary.md)
- [Manual test cases template](templates/manual-test-cases.md)

For example:

```bash
mkdir -p docs/phases/PUB-002-short-name
cp docs/phases/templates/task-summary.md \
  docs/phases/PUB-002-short-name/task-summary.md
cp docs/phases/templates/manual-test-cases.md \
  docs/phases/PUB-002-short-name/manual-test-cases.md
```

Replace all placeholders before opening the pull request.

## When phase documentation is required

Add or update a phase package for work that introduces one or more of these:

- a significant user or operator capability;
- a new external provider, integration, API, data model, or migration;
- remote writes, permissions, credentials, or another meaningful security boundary;
- coordinated changes across multiple components;
- operational behavior that needs manual acceptance, rollout, or rollback instructions.

A new phase package is normally unnecessary for typo fixes, dependency-only maintenance,
small internal refactors with unchanged behavior, or a narrow bug fix already covered by
an existing phase. For those changes, the pull request must state why phase documentation
is not applicable and still include proportionate automated or manual verification.

## What belongs in Git

Commit information that another contributor can safely reuse:

- background, scope, constraints, requirements, decisions, and architecture;
- synthetic examples with fake domains, IDs, tokens, users, and content;
- manual test definitions and sanitized execution results;
- links to automated tests and public documentation;
- known limitations, risks, and follow-up work.

Keep local or private:

- `.env` files, credentials, access tokens, and secret-manager paths;
- real Notion page IDs, Confluence space IDs, private URLs, or organization structure;
- raw reports, logs, screenshots, or API responses that may contain private data;
- customer documents, production data, or personally identifiable information.

The repository already ignores `.env`, `config/wiki_publish_map.json`, and `runs/`.
Before sharing evidence from an ignored path, create a sanitized summary instead of
committing the raw artifact.

## Task summary lifecycle

Create the task summary before implementation and update it as decisions are made. At the
end of the phase, record the implementation outcome, deviations, known limitations, and
verification evidence. Use `Not applicable` with a reason when a standard section does
not apply; do not silently remove the section.

Every functional, API, and non-functional requirement must have a stable ID. Every
acceptance criterion must link to at least one manual or automated test.

The task-summary template is intentionally comprehensive. Keep sections concise, merge
closely related requirements, and use `Not applicable — <reason>` where appropriate. The
goal is clear engineering evidence, not document length.

## Manual test lifecycle

Test definitions are public and reusable. An execution record adds these fields without
changing the expected behavior:

- status: `Not run`, `Passed`, `Failed`, `Blocked`, or `Skipped`;
- execution date and environment;
- tester or automation identity;
- sanitized actual result and evidence reference;
- issue link when the result failed or was blocked.

Use synthetic test data. Never place a valid password or token in a test case. Destructive
or externally visible cases must be clearly labeled and must use disposable resources.

Automated tests remain the preferred regression protection. Manual cases should focus on
real integrations, permissions, UI behavior, operational safeguards, and other behavior
that a mocked test cannot prove.

## Pull request integration

The repository's pull request template asks for the phase path, requirement IDs, automated
and manual verification, operational risk, rollback, and privacy review. Link the relevant
phase files rather than copying their full content into the pull request. If phase
documentation is not required, write `Not applicable` with a short reason instead of
leaving the field blank.
