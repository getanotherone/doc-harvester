# {PHASE-ID} Manual Test Cases: {Phase title}

> Replace every placeholder, then remove this note. Test definitions must use synthetic
> data. Never commit credentials, real private identifiers, private URLs, customer data,
> or unsanitized execution evidence.

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `{PHASE-ID}-TC-01` | `{What is verified}` | Critical / High / Medium / Low | Not run |

Allowed execution statuses: `Not run`, `Passed`, `Failed`, `Blocked`, or `Skipped`.

## Safety and test-data rules

- Use synthetic users, credentials, IDs, domains, and content.
- Clearly label destructive or externally visible cases and use disposable resources.
- State cleanup and rollback before executing a write test.
- Store raw evidence only in an approved private or ignored location.
- Commit sanitized results only; link an issue for every failed or blocked acceptance test.

---

### [{PHASE-ID}-TC-01] {Test case title: what is being verified}

- **Requirement IDs:** `{PHASE-ID}-FR-01`, `{PHASE-ID}-AC-01`
- **Component / Module:** `{component / module}`
- **Priority:** Critical / High / Medium / Low
- **Severity:** Critical / High / Medium / Low
- **Type:** Functional / Positive / Negative / Regression / Security / Performance / Accessibility / Recovery
- **Automation Status:** Manual only / Automated / Partially automated / Candidate for automation
- **Environment:** `{local, staging, OS, browser, device, API version, or service}`
- **Current Status:** Not run
- **Preconditions:**
  1. `{required initial state}`
  2. `{required permission, dependency, or fixture}`

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | `{one observable action}` | `{one unambiguous expected result}` |
| **2** | `{next action}` | `{next expected result}` |

- **Postconditions:** `{expected final state}`
- **Cleanup / Rollback:** `{how test data and external state are restored}`
- **Test Data:** `{synthetic values only}`

### Execution record

- **Status:** Not run
- **Executed:** `{YYYY-MM-DD or Not run}`
- **Tester:** `{name, handle, automation, or Not run}`
- **Actual Result:** `{sanitized observation or Not run}`
- **Evidence:** `{sanitized path/link/reference or Not run}`
- **Issue:** `{link for Failed/Blocked, otherwise Not applicable}`

---

<!-- Copy the complete test-case section above for each additional case. -->

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| `{PHASE-ID}-FR-01` | `{test file and test name, CI job, or Not automated — reason}` |

## Traceability review

- [ ] Every functional, API, and non-functional requirement has test or review coverage.
- [ ] Every acceptance criterion links to at least one manual or automated test.
- [ ] Negative, permission, boundary, recovery, and observability cases were considered.
- [ ] Destructive cases define disposable data and cleanup.
- [ ] Shared evidence is sanitized.
