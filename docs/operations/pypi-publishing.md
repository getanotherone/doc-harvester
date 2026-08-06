# Publishing doc-harvester to PyPI

This guide is for maintainers. Normal users install the package with
`pip install doc-harvester`; they do not need a PyPI account.

## One-time account setup

1. Create or sign in to an account at [PyPI](https://pypi.org/).
2. Verify the account email and enable two-factor authentication.
3. In GitHub, open the repository **Settings → Environments → New environment**.
4. Name the environment exactly `pypi`.
5. Add the primary maintainer as a required reviewer when the repository plan supports
   deployment protection rules. Do not add a PyPI API token as a GitHub secret.
6. In PyPI, create a pending Trusted Publisher for a new project with:

   | Field | Value |
   |---|---|
   | PyPI project name | `doc-harvester` |
   | GitHub owner | `getanotherone` |
   | Repository | `doc-harvester` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

The pending publisher reserves the publishing relationship, not the package name. Recheck
the project name immediately before the first release. Trusted Publishing exchanges the
GitHub workflow identity for a short-lived token; no reusable registry credential is stored.

## Release procedure

1. Merge a release pull request only after CI and review pass.
2. Confirm `pyproject.toml`, `doc_harvester.__version__`, README status, and changelog use
   the same version.
3. Create a GitHub release whose tag is exactly `v<version>`, for example `v0.2.1`.
4. Publish the GitHub release. Draft releases do not publish to PyPI.
5. Review and approve the `pypi` environment deployment if GitHub requests approval.
6. Verify the **Publish to PyPI** workflow completed both jobs.
7. Open `https://pypi.org/project/doc-harvester/` and confirm the expected version, project
   links, wheel, and source distribution are present.
8. In a new virtual environment, run:

   ```bash
   python3.11 -m venv /tmp/doc-harvester-pypi
   /tmp/doc-harvester-pypi/bin/python -m pip install doc-harvester==0.2.1
   /tmp/doc-harvester-pypi/bin/doc-harvester --version
   /tmp/doc-harvester-pypi/bin/doc-harvester demo \
     --output /tmp/doc-harvester-pypi-demo.json
   ```

## Failure and rollback

PyPI releases are immutable: an uploaded file or version cannot be replaced. If the build
or publish job fails, do not upload files manually to bypass the checks. Correct the cause,
increment the patch version when any artifact may already have reached PyPI, and publish a
new GitHub release.

If a published release is unsafe, yank it from PyPI, document the reason without exposing
sensitive details, and publish a corrected version. Deleting a GitHub release does not
remove a PyPI distribution.

## Security notes

- Keep `id-token: write` only on the publishing job.
- Review any third-party change to `.github/workflows/release.yml` especially carefully.
- Keep the `pypi` environment and Trusted Publisher names exact.
- Never paste PyPI tokens into issues, logs, `.env`, or repository secrets for this flow.
