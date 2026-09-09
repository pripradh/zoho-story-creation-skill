# Slicing and Sequencing

Read this before drafting any Sprint story (`collexo-prd-sprint` Step 3). Adapted from the team's Shift-Left Product Stories method for Collexo/Pixi PRD-to-Sprint conversion.

## Contents

1. Pre-writing analysis (release mode, behavior inventory, state matrix, boundaries, order)
2. The slicing method (five steps)
3. Live-release extension mode
4. Release sequencing rules
5. Dependency rules

---

## 1. Pre-writing analysis

Perform this silently, before writing a single story file. Most thin or generic Sprint stories trace back to skipping this.

### 1.1 Identify the release mode

Classify the PRD's request as one of:

- New capability
- Additive extension to a live capability
- Defect correction
- Behavior replacement
- Permission or access correction
- Runtime or data-integrity correction
- Reporting/observability-only change

The release mode drives scope, backward-compatibility expectations, sequencing, and which acceptance-criteria categories apply, so name it explicitly before slicing.

### 1.2 Extract the behavior inventory

Pull this from the whole PRD, not just Section 6 (User Stories):

Actor · Trigger · Entry point · Applicable records/entities · Applicable source states · Ineligible source states · Preconditions · Permissions · Limits · Payment mode or surface (admin / student portal / mobile) · System action · Persistence · Mapping rule · Resulting state · User-visible result · Failure behavior · Retry/duplicate behavior · Logs · Audit requirements (Section 21) · Out-of-scope behavior (Section 7)

Gaps in this inventory are what you flag as assumptions later, not what you silently fill in.

### 1.3 Build the state-transition matrix

For every stateful entity the feature touches, determine the trigger, the system outcome, the resulting state, and the user-visible result. Reuse the table from the PRD's Section 6/15 if the PRD already built one (`collexo-prd`'s Section 6 guidance now asks for this).

Example, for a credit-note-style entity:

| Source State | Trigger | System Outcome | Resulting State | User-visible Result |
|---|---|---|---|---|
| None | Punch (Cash/Cheque/DD/Bank Transfer/POS/Loan) | Credit note created | Unapplied | Appears in Credit Notes tab, full balance shown |
| Unapplied | Apply (partial) | Partial allocation persisted | Partially Applied | Remaining balance updates, applied portion reflected on the due |
| Partially Applied | Apply (remaining balance) | Full allocation persisted | Fully Applied | Balance shows zero, no further apply possible |
| Unapplied | Void | Reversed | Void | Removed from applicable balance, void reason recorded |
| Partially Applied | Void (attempted) | Blocked | No change | Existing error: cannot void a credit note with any applied amount |
| Fully Applied | Void (attempted) | Blocked | No change | Existing error: cannot void a fully applied credit note |

A story set must not leave an undefined transition for any applicable state.

### 1.4 Identify independent behavior boundaries

Create a separate story when behaviors differ materially in any of these dimensions:

- Different user intent (punch vs. void vs. apply vs. download)
- Different source state
- Different resulting state
- Different surface (admin vs. student portal vs. mobile app)
- Different failure policy
- Different release dependency
- Different permission model
- Different rollback risk
- Different reporting/cascade target
- Different observability requirement
- One behavior can release safely without the other

Do **not** create separate stories merely because different repos or codebases are involved, and never split a single behavior into an FE story and a BE story: request validation, persistence, and the user-visible result belong in one story together.

### 1.5 Determine release order

Order by product dependency, never by team ownership. Typical principles for Collexo features:

1. A resulting state must be safely actionable (viewable, void-able, apply-able as applicable) before another story starts producing it.
2. Eligibility and permission enforcement must exist before an action is exposed on any surface.
3. The admin-side creation/record-keeping behavior generally precedes the student-facing display of the same record.
4. Status mapping must exist before any UI relies on the mapped status.
5. Reporting-cascade stories (Payment Ledger, Applicant Profile, etc.) depend on the underlying record existing and being stable, so sequence them after the core punch/void/apply stories, not before.
6. Permission-split or migration stories must land before the capability they gate is exposed on any surface.
7. Observability/log stories needed for safe production diagnosis should land alongside (not after) the behavior they log.

Explain the ordering briefly whenever it is not self-evident.

---

## 2. The slicing method

### Step 1: Define the smallest complete behavior

Ask: *what is the smallest behavior that can be released, exercised, and retained safely in production?* The answer is a candidate story.

### Step 2: Test story independence

A story is independently releasable only if every answer is yes:

- Can it deploy without another unreleased story?
- Can the admin, student, or system reach the behavior safely?
- Are required permissions enforced?
- Are invalid requests blocked?
- Is its resulting state supported (viewable/actionable, not a dead end)?
- Can QA test it independently, given zero automated coverage platform-wide?
- Are failures understandable?
- Are partial writes prevented?
- Does existing live behavior continue working?
- Can the story remain live if the next story is delayed?

Any "no" means either add the missing behavior to the story, or introduce an earlier independently releasable prerequisite story.

### Step 3: Test end-to-end completeness

Check the story covers: entry point · visibility · permission · eligibility · request · processing · persistence · response · refresh · error state · retry · limit · logs · negative path.

Do not assume the "existing flow" covers a changed source state unless the acceptance criteria explicitly confirm it.

### Step 4: Remove technical decomposition

Review every title. If it names a technical component rather than a behavior, rewrite it.

Wrong:

```text
Advance Payment | Add API for Punch
Advance Payment | DB Table for Credit Note
Advance Payment | FE Button for Add Advance Payment
Advance Payment | BE Persist Credit Note
```

Right:

```text
Advance Payment | Punch a Cash/Cheque/DD/Bank Transfer/POS Advance Payment
Advance Payment | Void an Unapplied Credit Note
Advance Payment | Apply a Credit Note to a Due (Partial)
```

### Step 5: Remove duplicate scope

Every behavior has exactly one primary story. Later stories may depend on it but must not restate it as new scope. If one story makes a credit note void-able, a later story that lets void happen from a different surface may depend on it but must not claim to introduce void again.

---

## 3. Live-release extension mode

When the PRD is an additive extension to a capability already live (e.g. adding a new source type to an existing credit-note entity), declare:

```text
Release Mode: Additive extension to an existing live capability
```

Then:

- Write only the new stories.
- Start numbering after the existing sequence when the numbers are known.
- Do not recreate earlier stories or restate delivered scope as new work.
- Mention existing behavior only as dependency, preserved behavior, or context.
- Identify clearly the delta each new story introduces.

### 3.1 Start from the delta

Establish: what new case was missed, what live behavior remains correct, what exact condition changes, which existing contracts are reused (e.g. the existing "Marking Payment from Credit Note" apply mechanism), and which existing rules stay untouched.

### 3.2 Preserve existing contracts

Unless the PRD explicitly changes it, retain the existing API contract, action placement, permissions, limits, status matrix, page-refresh behavior, error-display behavior, analytics, logs, and any existing exclusions.

### 3.3 Add regression scenarios

Every additive story needs acceptance criteria confirming that existing eligible cases still work, existing ineligible cases stay blocked, unrelated sources/vendors/modes are unchanged, existing permissions and limits are unchanged, and crafted requests cannot bypass the new rule.

### 3.4 Do not reopen delivered decisions

A new story must not redesign an existing decision unless the PRD explicitly changes it. Adding a new source type to a credit note must not reopen void mechanics, permission ownership, apply mechanics, or page placement.

---

## 4. Release sequencing rules

When multiple stories are produced, include a sequence section (this feeds `collexo-prd-sprint` Step 5):

```markdown
## Story Sequence

1. Punching of Advance Fees | Story 1 | Punch a Cash/Cheque/DD/Bank Transfer/POS Advance Payment
2. Punching of Advance Fees | Story 2 | Void an Unapplied Credit Note
3. Punching of Advance Fees | Story 3 | Apply a Credit Note to a Due (Partial)
```

Then explain only the real dependency:

```text
Story 1 must release before Story 2 because Story 2 acts on the record Story 1 creates.
Story 1 must release before Story 3 for the same reason.
```

Never sequence by team preference, "UI before API", "backend before frontend" as a generic rule, estimated effort, or story-number aesthetics. Sequence by safe product behavior.

---

## 5. Dependency rules

A dependency is valid only when the story cannot release without it.

Valid:

- An existing live capability (e.g. the existing "Marking Payment from Credit Note" apply mechanism)
- An existing page permission
- Story 1, because Story 2 acts on the state Story 1 produces
- Existing void/void-reason storage
- Authoritative backend permission configuration

Invalid:

- The frontend team
- The backend team
- QA availability
- General engineering effort
- Every other story in the epic, absent a direct dependency

Keep dependencies minimal and exact.
