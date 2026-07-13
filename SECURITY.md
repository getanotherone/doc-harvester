# Security Policy

## Supported versions

Until the first stable release, security fixes are applied only to the latest `main`
branch and most recent tagged alpha release.

## Reporting a vulnerability

Use GitHub's private security-advisory feature for the repository. If it is unavailable,
contact the maintainer privately through the address listed in the maintainer's GitHub
profile. Do not include credentials, private documents, or exploit details in a public
issue.

Include affected versions, reproduction steps, impact, and any suggested mitigation.
You should receive an acknowledgement within seven days.

## Credential handling

- Secrets must come from environment variables or a secret manager.
- `.env`, local Wiki page maps, browser session state, and generated run data are ignored.
- Rotate a credential immediately if it appears in logs, issues, commits, or artifacts.
- Test credentials and examples must be obvious non-secret placeholders.

## Deployment warning

The crawler processes untrusted remote content. Run it with limited filesystem and
network permissions, bounded resource limits, and isolated OCR/browser processes.
