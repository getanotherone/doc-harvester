# First-user and contributor launch

The first goal is not a large star count. It is evidence that people outside the maintainer's
environment can install the package, understand its purpose, complete the demo, and report
useful feedback.

## Initial success signals

- Three to five independent people complete the credential-free demo.
- At least one person tries a real, legally usable document or public documentation site.
- At least one external issue, discussion, documentation fix, or pull request is received.
- Feedback produces one documented improvement and follow-up release.

These are internal launch targets, not claims about active users and not eligibility rules
for any external program.

## Launch checklist

1. Publish and clean-install the PyPI release.
2. Open two or three small issues with reproducible context, acceptance criteria, likely
   files, and exact test commands; label them `good first issue` and `help wanted` where
   appropriate.
3. Invite a small group of relevant Python, RAG, documentation, or data-engineering users
   to run the five-minute demo.
4. Ask for one concrete observation: installation friction, confusing output, missing
   documentation, or a failed document type.
5. Share in communities only where project posts are allowed. Lead with the problem solved,
   current limitations, and the credential-free demo rather than asking for stars.
6. Respond promptly, reproduce reports with synthetic/public inputs, and convert confirmed
   feedback into scoped issues.

## Suggested first contribution areas

- Add a small synthetic fixture for an extractor edge case.
- Improve one actionable CLI error and its regression test.
- Add a provider-neutral discovery profile example.
- Test an S3-compatible provider using synthetic data and document sanitized results.
- Clarify a confusing quick-start or troubleshooting step.

Do not label an issue `good first issue` merely because it is low priority. It should have a
small scope, a clear expected result, and enough context for a new contributor to succeed.

## Feedback record

Track public technical feedback in GitHub issues. Do not publish email addresses, private
messages, private source URLs, customer documents, or personal analytics. A future program
application should cite verifiable releases, public issues, contributions, and aggregate
package usage without describing downloads as confirmed human users.
