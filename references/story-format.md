# Story Format and Section Rules

Read this while drafting Sprint stories (`collexo-prd-sprint` Step 4). Adapted from the team's Shift-Left Product Stories method. The locked template in `SKILL.md` Step 4 is the one to actually use; this file explains the rules behind each section.

## Contents

1. Title rules
2. Team field
3. User story statement rules
4. Description rules
5. Acceptance criteria standard and mandatory scenario categories
6. Example cases
7. Validations
8. Logs and observability
9. Out-of-scope rules
10. Non-functional requirements

---

## 1. Title rules

A story title must begin with the product capability or feature, include the story number when a sequence exists, and describe the released behavior. Avoid implementation terminology, vague labels such as "Enhancement", "Handling", or "Changes", and unrelated outcomes joined by "and".

Good:

```text
Punching of Advance Fees | Story 2 | Void an Unapplied Credit Note
Punching of Advance Fees | Story 6 | Show the Credit Notes Sidebar Page on Student Portal
```

Weak:

```text
Advance Payment Changes
Void Handling
Button and API Update
FE/BE Changes for Credit Notes
```

---

## 2. Team field

`TEAM` names the product the story belongs to: `Collexo`, `Pixi`, or `Nexeo`. It is
separate from `MODULE / EPIC`, which names the feature area within that product.
Set it from the PRD's own product, not from the Zoho project key.

---

## 3. User story statement rules

The statement must explain the actual behavior and outcome. Do not force a fake end user when the story protects the platform, the ledger, or a downstream report. Valid actors include an institution admin, a counter/ops staff member, a student, the payment platform itself, a support user, a security administrator, or a data-migration process.

```text
As an institution admin,
I want to void an advance payment credit note that has no applied amount,
So that I can correct a mistaken or duplicate entry before it reaches a student's fees.
```

```text
As the payment platform,
I want an advance payment credit note's void to be blocked once any amount has been applied,
So that a partially or fully consumed credit note can never leave the ledger in an inconsistent state.
```

---

## 4. Description rules

The description must establish: current behavior, the gap, the exact new behavior, applicability, existing behavior reused, existing behavior unchanged, and explicit exclusions.

For a live extension, use language such as:

```text
The Credit Notes tab and Mark Offline flow are live. This story adds a new "Add Advance
Payment" entry point that creates a credit note with no fee head required at creation.
All existing refund-conversion credit note behavior, permissions, and the existing
"Marking Payment from Credit Note" apply mechanism remain unchanged.
```

Avoid descriptions that merely restate the user story.

---

## 5. Acceptance criteria standard

Criteria must be behavioral, observable, deterministic, testable, state-aware, permission-aware, limit-aware, and safe against bypass. Use `GIVEN / WHEN / THEN`.

Number every scenario and label it with a short situational tag instead of the bare category name below, e.g. "Scenario 1 - Valid configuration", "Scenario 2 - Invalid configuration", "Scenario 3 - Direct request". The category names in 5.1 are what must be covered, not the literal label to print.

### 5.1 Mandatory scenario categories

Include every category that materially applies to the story; do not force one that doesn't, but do not drop one that does:

**Primary behavior**: eligible user performs the action; expected system outcome occurs; user-visible result updates.

**State transitions**: every applicable source state; every possible resulting state; same-state result; invalid transition (e.g. attempting to void a Partially Applied credit note).

**Boundary conditions**: no limit configured vs. a configured limit reached; missing optional value (e.g. no student contact details); missing required identifier (e.g. no Application Number).

**Permissions**: authorized user (holds the relevant permission); unauthorized user; crafted API request without the permission.

**Surface isolation**: where a behavior applies to only one surface (admin / student portal / mobile), confirm the other surfaces are unaffected or correctly show the read-only/adapted view.

**Failure handling**: targeted business error (e.g. currency mismatch); persistence failure; malformed input; network/timeout where an external call is involved.

**Data integrity**: atomic update; no partial state; duplicate request (e.g. double-clicking Void); repeated same response; stale frontend state (e.g. balance shown before a concurrent apply).

**Regression protection**: existing statuses unchanged; existing permissions unchanged; existing limits unchanged; other credit-note sources (e.g. refund conversion) unaffected; other actions remain operational.

### 5.2 Do not over-specify unsupported technical detail

Do not invent HTTP status codes, table names, column names, queue names, lock technology, retry counts, timeout values, or API fields unless the PRD or an established platform contract provides them (check the relevant module summary in `_context/module-summaries/` first).

Write at behavior level:

```text
The credit note's status and remaining balance must update atomically on apply.
```

Not:

```text
Use a transaction on the credit_note table's remaining_credit_amount column.
```

---

## 6. Example cases

After the acceptance criteria, add one or more concrete worked examples that ground
the Given/When/Then scenarios in an actual instance, not a restatement of them.
Format: "Case N: <concrete situation>. <system's actual response>." For example:

```text
Case 1: A builder attempts the invalid form of a branch ending in Remove Record.
The system blocks it and leaves the canvas unchanged.
```

One example case is enough when the story has a single clear failure mode; add more
when different scenarios need distinct worked examples to be unambiguous.

---

## 7. Validations

Validations protect the behavior at the authoritative system boundary. Typical ones for Collexo credit-note-family features: page or action permission · current credit note state (Unapplied/Partially/Fully Applied/Void) · required identifiers (Application Number) · currency match between credit note and target fee head · payload integrity · ownership/institution scoping · duplicate request · atomic persistence.

Frontend validation improves usability; backend validation enforces the product rule. Describe both inside one story, never as separate FE and BE stories. Note explicitly where the platform's zero-automated-test-coverage constraint means a validation needs manual QA regression coverage.

---

## 8. Logs and observability

Add logs when the behavior involves state changes, financial impact, credits or reversals, permissions, or data correction; this covers most of the credit-note/advance-payment family.

Log only what is needed. Typical fields for this domain: credit note ID · institution/college ID · application number · previous state · requested action (punch/void/apply) · applied amount · resulting state · actor · timestamp. Cross-check against the PRD's Section 21 (System Audit Activities): if that section already scopes an activity as logged via an existing mechanism, cite that mechanism here rather than inventing a new one.

Do not require attachment or document content (e.g. the proof-of-payment upload) in logs unless the PRD explicitly permits it. Flag any PII the attachment itself may carry (bank account numbers, IFSC, signatures) per the PRD's Section 13/15 guidance.

---

## 9. Out-of-scope rules

Out of scope prevents accidental expansion, so include closely adjacent behaviors a reader might otherwise assume are included, for example: bulk void, bulk apply, maker-checker approval (if parked per the PRD), editing an applied credit note in place, changing permission defaults, applying a vendor-specific rule to other sources.

Do not add random exclusions unrelated to the story.

---

## 10. Non-functional requirements

Include only applicable NFRs, each testable.

**Security**: when permissions, crafted requests, or sensitive data (attachment PII, bank details) are involved. *Backend-owned permission configuration is authoritative; UI visibility does not replace backend permission enforcement.*

**Atomicity**: when multiple fields or records must stay consistent. *Credit note status and remaining balance commit together; no partial allocation remains after a failed apply.*

**Idempotency**: when actions can repeat. *Repeating the same apply/void request leaves one consistent state; duplicate requests do not create duplicate credit notes.*

**Backward compatibility**: for live-release extensions. *Existing refund-conversion credit notes and their permissions remain unchanged.*

**Observability**: for operationally important flows. *Logs identify previous state, action, actor, and final state.*

**Performance**: only when the behavior can materially affect latency or throughput (e.g. the reporting cascade into Payment Ledger, given its known timeout risk on large entities). Never "the system should be fast."

**Accessibility**: when user-facing controls, errors, or navigation change on any surface.

**Privacy**: when logs, attachments, or applicant/student data are involved.
