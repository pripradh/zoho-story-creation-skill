# Quality Gates, Failure Patterns, and Definition of Done

Read this before running `collexo-prd-sprint` Step 6. Run every story through the gates below before punching anything into Zoho.

---

## 1. Quality gates

### 1.1 Independent release gate

- [ ] Can release without exposing incomplete behavior
- [ ] Can remain live if the next story is delayed
- [ ] Resulting states are supported (viewable/actionable, not a dead end)
- [ ] User is not trapped in a dead end (e.g. a credit note stuck in a state nothing can act on)
- [ ] Invalid requests are blocked
- [ ] Permissions are enforced
- [ ] Limits are enforced (or explicitly "no limit" per the PRD)
- [ ] Failure behavior is defined

### 1.2 End-to-end gate

- [ ] Entry point defined (which surface, which action)
- [ ] Eligibility defined
- [ ] Action defined
- [ ] System processing defined
- [ ] Persistence defined
- [ ] User-visible result defined
- [ ] Retry/repeat behavior defined
- [ ] Error display defined
- [ ] Logs defined where required

### 1.3 Shift-Left gate

- [ ] No FE/BE split
- [ ] No team-based split
- [ ] No fake customer-value claim for a platform-safety story (e.g. a reporting-cascade story doesn't need an invented "so the student feels great" justification)
- [ ] No technical task disguised as a story ("add API", "add DB column")
- [ ] No feature flag invented where none exists
- [ ] No hidden dependency
- [ ] No partial state
- [ ] No untested negative path
- [ ] No silent assumption: anything genuinely undecided is flagged, not guessed
- [ ] No unrelated scope

### 1.4 Live-release regression gate

Apply this gate whenever the story extends an already-live capability (e.g. adding advance-payment as a new credit note source alongside the existing refund-conversion source):

- [ ] Only new behavior is presented as new scope
- [ ] Existing eligible cases remain unchanged
- [ ] Existing ineligible cases remain unchanged
- [ ] Existing permissions remain unchanged
- [ ] Existing limits remain unchanged
- [ ] Other credit-note sources/modes remain unchanged
- [ ] Existing contracts (API, page placement, notification behavior) remain compatible

---

## 2. Common failure patterns

### 2.1 Mechanical FE/BE splitting

Bad:

```text
Story 1: Add backend validation for Void
Story 2: Add frontend Void button
```

Neither story necessarily produces a complete release, the admin may see an unsupported action, and QA cannot validate the product outcome independently. Instead create one behavioral story covering both user feedback and authoritative enforcement. Split only when each resulting story is itself a complete releasable behavior.

### 2.2 Writing tasks instead of stories

"Create endpoint", "add enum", "update database", "add button", "write unit tests" are implementation tasks under a story, not product stories.

### 2.3 Restating the entire existing release

When a capability is live (e.g. the existing Credit Note / Mark Offline mechanism), do not reproduce earlier stories for it. Write only the additional delta this PRD introduces.

### 2.4 Producing an unsupported resulting state

Bad sequence: a story starts creating credit notes in the Unapplied state, and a later story is what makes Unapplied credit notes visible/actionable in the Credit Notes tab. That temporarily creates a dead end: a record exists that nothing can act on or even see.

Correct sequence: make the resulting state safely actionable first (or bundle visibility into the same story), then introduce the path that produces it.

### 2.5 Inferring policy not stated in the PRD

Do not assume a validation, limit, or notification rule applies just because it seems reasonable. Ground every validation and NFR in what the PRD actually locked (its Decisions Log, Section 11 Permissions, Section 15 Technical Notes); if the PRD is silent, flag it as an open question rather than inventing the rule.

### 2.6 Treating UI visibility as security

Hiding an action (e.g. hiding the Void action in a menu) is not permission enforcement. Always include authoritative backend request validation for permission, eligibility, state, and limits within the same end-to-end story.

### 2.7 Missing regression scenarios

Every live-release extension must prove that unrelated sources, statuses, permissions, and flows remain unchanged. This matters especially here since Collexo has zero automated test coverage platform-wide, so these scenarios are what QA's manual regression pass is actually built from.

### 2.8 Excessive generic NFRs

Bad:

```text
The system should be scalable and secure.
```

Good:

```text
Void must be blocked authoritatively on the backend once remaining_credit_amount is
less than the original credit note amount, regardless of what the frontend displays.
```

---

## 3. Definition of done

The story set for a PRD is complete only when:

- Every requested behavior in the PRD is represented
- No requested behavior is duplicated across stories
- No story is a technical task
- No story depends on unreleased hidden behavior
- Every introduced state is usable at the point it's introduced
- Permissions and limits are enforced per the PRD's Section 11/10
- Crafted requests are handled
- Partial persistence is prevented
- Repeat/duplicate behavior is defined
- Existing live behavior is protected (for any additive extension)
- Release order is safe and its rationale is stated
- QA can execute each story independently, given zero automated coverage
- Dev and QA can implement without guessing the intended behavior
