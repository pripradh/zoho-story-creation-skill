---
name: collexo-prd-sprint
description: Create the Zoho Sprints sprint and stories for a Collexo/Pixi PRD that has already been written, confirmed, and frozen. Slices the PRD's user stories into detailed, independently releasable, implementation-ready stories (Shift-Left method) before punching them into Sprints, not a flat 1:1 copy of the PRD's own user-story list. Use this only after the user has explicitly signed off on the final PRD content; never mid-draft, never as an automatic continuation of the collexo-prd skill. Trigger for requests like "create the sprint stories for X" or "punch this PRD into Sprints" once the PRD itself is done.
---

# Collexo PRD → Sprint Stories

Creates a brand-new Zoho Sprints sprint (named after the PRD) and a set of detailed, independently releasable stories derived from the PRD, directly via the Sprints API. This is a deliberately separate skill from `collexo-prd`: do not fold this back into that skill's run, and do not invoke it as the automatic next step after publishing a PRD Doc.

**The PRD's own Section 6 user stories are the starting inventory, not the final story list.** This skill runs its own slicing pass (Step 3) before writing anything: the PRD is a stakeholder-readable narrative, while the Sprint stories are the implementation-ready artifact Dev and QA actually build and test from. A PRD with 5 narrative user stories can reasonably produce 15–25 sliced Sprint stories once split by independent release boundary. Do not skip the slicing pass and copy PRD stories 1:1.

---

## Gate: Only Run This After the PRD Is Confirmed and Frozen

This is the most important rule in this skill.

- **Never run this mid-draft.** Sprint stories must reflect the final, confirmed content of the PRD, not a working draft that might still change. Creating stories early means they silently drift out of sync with the PRD as it's iterated, and nobody notices until sprint planning.
- **Wait for an explicit signal from the user** that the PRD is confirmed and frozen (e.g. "this is final", "let's create the stories now", "PRD is approved"), not just that the Google Doc was published. Publishing the Doc is necessary but not sufficient; a published Doc can still be mid-review.
- **If invoked while a PRD is still open for edits, say so and stop.** Don't proceed "just in case it doesn't change." Ask whether the PRD is actually final first.

---

## Writing Style: No Em Dashes

Hard rule from the workspace's root CLAUDE.md, restated here because it has been missed before. Never use an em dash ("—"), a double hyphen ("--"), or the HTML entity `&mdash;` anywhere in a story file, a sprint description, or this skill's own output. Use a comma for a short aside, a colon when what follows explains what precedes it, a semicolon for two closely related independent clauses, two full sentences for two separate thoughts, or parentheses for a true parenthetical. Before running Step 7, search every story file for "—", "&mdash;", and "--" and confirm zero matches.

---

## Writing Style: Plain Language

Every story must read in plain, simple English: someone with no technical background should be able to follow the User Story Statement, Description, and Acceptance Criteria on a first read. This applies to every section, not just the narrative ones.

- Short sentences, one idea each. Break up any sentence carrying more than one clause joined by "which," "since," "so that it," or a comma-spliced aside.
- No dense multi-clause prose. If a sentence needs a semicolon to hold two ideas together, split it into two sentences instead.
- Plain everyday words over formal or academic ones, except for the technical terms the contract itself defines (client_code, api_key, entity_id, and so on) - keep those, since inventing a plainer synonym for a wire-locked term is worse than using the real one.
- Read every section back before Step 7 and ask: would someone outside engineering, reading this for the first time, understand it without re-reading? If not, rewrite it, don't just trim it.

This is not optional polish. A story written in dense, jargon-heavy prose fails the same way a technical-task-disguised-as-a-story fails: Dev and QA end up guessing the intended behavior instead of reading it directly off the story.

---

## Step 0: Verify the Zoho Sprints Connection

Before doing any slicing or story-writing work, confirm the Zoho Sprints connection is actually set up. Do not discover a missing connection only when Step 7 tries to punch stories in, after all the analysis work is already done.

Run:
```bash
python3 create_prd_sprint_item.py --check-setup
```
(from `scripts/` in this repo)

This checks for a usable `.env` (via `--env-file`, `ZOHO_SPRINT_ENV`, or a colocated `.env` in `scripts/`, in that order) and actually exchanges the refresh token for an access token, so a stale or revoked credential is caught here too, not just a missing file.

- **If it prints `OK`**, proceed to Step 1.
- **If it fails**, stop here and walk the user through `scripts/README.md`'s "Get Zoho OAuth credentials" section before continuing: creating a Zoho self-client, generating `ZOHO_CLIENT_ID`/`ZOHO_CLIENT_SECRET`/`ZOHO_REFRESH_TOKEN`, copying `scripts/.env.example` to `scripts/.env`, and filling in the values (plus `ZOHO_DC` if the org isn't on the India datacenter). Re-run `--check-setup` until it passes. Do not attempt to slice or write stories while the connection is unconfirmed.

## Step 1: Confirm Inputs

Before creating anything, confirm you have:
1. The finalized PRD (the published Google Doc, or the approved HTML preview if the Doc step hasn't run yet; either is fine as long as it's marked final).
2. The feature/PRD name: this becomes the new sprint's name, verbatim.
3. The target project: `collexo-team1` (Collexo_Team_1) for Collexo PRDs, `pixi-team1` (Pixi_Team_1) for Pixi PRDs. Never `collexo-bugs` / `bugs-issues`, since those are bug-tracking projects, not where PRD stories belong.

## Step 1b: First-Time Project Setup (New Projects Only)

Skip this step entirely if the target project from Step 1 already has an entry in `sprint_config.json` (true for `collexo-team1` and `pixi-team1` today). Run it once, the first time this skill is ever pointed at a project that isn't in there yet - after that, every future PRD for that project skips straight to Step 2.

The goal: discover everything the Zoho API can tell us live, and ask the user directly only for the handful of things it genuinely can't. Never guess a value that should come from one of these two sources.

1. **Which Zoho project.** Ask the user for the Zoho Sprints project's exact display name (not a key you invent). Then run:
   ```bash
   python3 create_prd_sprint_item.py --discover-project "<Zoho project display name>"
   ```
   This is fully live and needs no local data: it matches the name against the team's live project list and prints `name`, `project_id`, `backlog_id`, `item_types`, and `priorities`, ready to paste into a new project block in `sprint_config.json`. If the name doesn't match, it prints every live project so the user can pick the right one. Ask the user what local key to file it under (e.g. `meritto-team1`) - that key is your own naming choice, not Zoho data.

2. **Pick defaults.** From the discovered `item_types`/`priorities`, ask the user which one this script should use when a PRD doesn't specify one (a policy choice - there's no API-correct answer). Add as `"defaults": {"item_type": "...", "priority": "..."}`.

3. **Owner fields.** This is the one piece that is **not** discoverable from any API tested (confirmed 2026-08-31: the live form-fields endpoint doesn't expose the internal `UDF_*` field codes at all). Ask the user directly: does this project share the same custom field layout as `collexo-team1`/`pixi-team1` (the `planned-release` family - QA Owner `UDF_USERPKL2`, Dev Owner `UDF_USERPKL3`, Task Type `UDF_PKL4`)? If yes, add that same `"owner_fields"` block. If unsure or no, skip `"owner_fields"` for this project for now - the script runs fine without it (QA Owner/Dev Owner/Task Type simply won't be set on created items until someone confirms the real field codes, e.g. by checking Zoho Sprints' admin custom-field settings or cross-referencing one live item the way `collexo-team1`'s were originally confirmed).

4. **Owner defaults.** Only if Step 3 above resolved real `owner_fields`, run:
   ```bash
   python3 create_prd_sprint_item.py --discover-owner-defaults --project <key>
   ```
   Live backlog sample, no local data needed. Present the suggestion to the user and confirm before adding `"owner_defaults"` - the statistically top candidate isn't automatically the right default.

5. **Epics.** Run:
   ```bash
   python3 create_prd_sprint_item.py --discover-epics --project <key>
   ```
   Live, one cheap call. Every `UNKNOWN` epicId needs the user to open one of the printed example items in the Zoho Sprints UI and read its Epic field (names aren't fetchable via any API on this credential set - confirmed 2026-08-31, scope-blocked). Add confirmed names to that project's `"epics"` block. Epics nobody has scoped a PRD to yet can stay unnamed until they're needed.

Once these are in `sprint_config.json`, proceed to Step 2.

## Step 2: Resolve the Epic

Every story in the new sprint should map to whichever *existing* epic in the target project the PRD's feature area best fits. Never invent a new epic per PRD or per sprint.

- Infer the best-fit epic from the PRD's content against the target project's known epics.
- **If the fit is clearly the single best match, use it.** If two or more epics are plausible, present the shortlist to the user and confirm before creating any items; do not guess between close candidates.
- **Known epics live in `sprint_config.json`**, under each project's `"epics"` block (`{epicId: name}`); that file is the source of truth, not this skill. Do not restate specific epic IDs or names here; if a list is ever written into this doc, treat it as already stale and go check the config instead.
- **Finding an epic's ID:**
  1. Check `sprint_config.json`'s `"epics"` block for the target project first - if the epic is already named there, use its ID directly.
  2. If it isn't (a new epic, or one not yet confirmed), run `python3 create_prd_sprint_item.py --discover-epics --project <key>` (from `scripts/` in this repo). This is a single live, read-only call (`epicId` is a standard field, already populated in the cheap bulk list response, so no local sync data is needed) that lists every epicId actually in use on that project's backlog, marking each as already-named or `UNKNOWN`.
  3. Zoho's dedicated "Get epics" API is blocked by a missing OAuth scope on this credential set (confirmed live 2026-08-31, `401 Invalid oauthscope`), so an `UNKNOWN` epicId's *name* can't be fetched automatically. Open one example item the command prints for that epicId in the Zoho Sprints UI, read its Epic field, and add `"<epicId>": "<name>"` to that project's `"epics"` block in `sprint_config.json` yourself. Once added, every future run (any PRD, any session) recognizes it - each epicId only needs naming once, ever.
- Once resolved, note which epic this specific PRD used in that PRD's own `CLAUDE.md` decisions log (that's per-PRD provenance, distinct from the master epicId→name mapping which stays solely in `sprint_config.json`).

## Step 3: Slice the PRD Into Independently Releasable Stories

Read `references/slicing-and-sequencing.md` before doing this. Do this analysis silently before writing a single story.

Do not map PRD Section 6 stories 1:1 into Sprint stories. Instead:

1. **Classify the release mode** (new capability, additive extension to a live capability, defect correction, permission correction, etc.) and name it explicitly.
2. **Extract the behavior inventory** from the whole PRD (not just Section 6): every actor, trigger, entry point, applicable state, permission, limit, vendor/integration route, failure/retry/duplicate behavior, log, and out-of-scope item. Pull this from Section 5 (User Flows), Section 6 (User Stories), Section 11 (Permissions), Section 15 (Technical Notes), and Section 21 (System Audit Activities) together, since a PRD's real behavior inventory is usually spread across several sections, not contained in Section 6 alone.
3. **Build the state-transition matrix** for every stateful entity the feature touches (reuse the table from PRD Section 6/15 if one exists there).
4. **Find independent behavior boundaries**: split into a separate story wherever user intent, source state, resulting state, permission model, failure policy, or release dependency differs materially. Do not split by technical layer (never an FE story and a BE story for the same behavior), and do not split merely because different repos or teams are involved.
5. **Default to the smaller side of any boundary** (`references/slicing-and-sequencing.md` § 1.4a): when a boundary from step 4 could justify a split, split it, rather than bundling multiple outcomes into one card "to keep the count down." This is the default on the first pass, not a granularity level to confirm with the user each time. Only raise it with them when a PRD's shape genuinely doesn't fit the common patterns § 1.4a describes (success path, distinct non-success resulting states, a combined reject-invalid-call story per endpoint, safe-repeat behavior, permission-conflict checks, emergent cross-story consequences).
6. **Let story count emerge from this analysis.** It is not a target to hit or a count to minimize: a feature with several independent behaviors should produce several stories, each small enough to release, test, and leave live on its own.

## Step 4: Write Each Story in the Locked Format

Read `references/story-format.md` before writing. **Story format (locked, use for every story created):**

Every section below, not just the narrative ones, must be written in plain English a non-technical reader can follow on a first read: short sentences, one idea each, no dense multi-clause prose. See "Writing Style: Plain Language" above. This is not a separate pass done after the content is right; write it plainly the first time.

```
--- STORY HEADER ---
STORY ID: <Epic/Feature> | Story <N> | <short Title Case description of the released behavior, e.g. "Void an Unapplied Credit Note">
MODULE / EPIC: <resolved epic from Step 2>
TEAM: Collexo, Pixi, or Nexeo, whichever product the PRD belongs to
PRIORITY: P0/P1/P2/TBD
STORY POINTS: TBD
FEATURE FLAG: None (<reason>), or the actual flag if one exists

--- USER STORY STATEMENT ---
As a [role/persona/system actor],
I want to [complete, independently releasable behavior],
So that [user, operational, compliance, or integrity outcome].

--- DESCRIPTION ---
[Current behavior, the gap, the exact new behavior, what's reused unchanged,
what's explicitly excluded. 2-5 lines, but do not compress away a real boundary.]

--- PREREQUISITES ---
[Required live capability, configuration, permission, identifiers, or prior story
this one depends on. Only real dependencies; never "the frontend team" or similar.]

--- USER / SYSTEM FLOW ---
[Numbered, step-by-step: entry point, validation, system action, external/vendor
interaction if any, persistence, refresh, user-visible outcome.]

--- ACCEPTANCE CRITERIA ---
Given/When/Then (Gherkin). Number every scenario and label it with a short situational
tag instead of the bare category name, e.g. "Scenario 1 - Valid configuration",
"Scenario 2 - Invalid configuration". Include every category below that materially
applies to this story; do not force a category that doesn't apply, but do not drop
one that does:

Scenario N - <situational tag>: Primary behavior
Scenario N - <situational tag>: State transitions (every applicable source state, every resulting state,
  same-state result, invalid transition)
Scenario N - <situational tag>: Boundary conditions (limit not reached / exact limit / limit exceeded /
  missing optional value / missing required identifier)
Scenario N - <situational tag>: Permissions (authorized user / unauthorized user / crafted request without
  permission)
Scenario N - <situational tag>: Failure handling (targeted business error / timeout / malformed input /
  persistence failure)
Scenario N - <situational tag>: Data integrity (atomic update, no partial state, duplicate request,
  stale frontend state)
Scenario N - <situational tag>: Regression protection (existing states/permissions/limits/flows unchanged,
  for any story extending live behavior)

--- EXAMPLE CASES ---
[One or more concrete worked examples that ground the acceptance criteria in an
actual scenario. Format: "Case N: <concrete situation>. <system's actual response>."
Not a restatement of the Given/When/Then; a plain-language instance of it.]

--- VALIDATIONS ---
[Eligibility, permission, state, limit, configuration, payload, atomicity,
whichever apply. Cover both frontend usability validation and the authoritative
backend enforcement in the same story, never as separate stories.]

--- LOGS ---
[Only when the behavior involves state changes, financial impact, credits/reversals,
permissions, or data correction. Typical fields: record/entity ID, previous state,
requested action, mapped outcome, final state, actor, timestamp.]

--- OUT OF SCOPE ---
[Explicitly what this story does NOT cover. Include closely adjacent behavior a
reader might otherwise assume is included, not just unrelated exclusions.]

--- DEPENDENCIES ---
[Only real dependencies: an existing live capability, a permission, another story
in this same sequence that this one needs already released. Never a team or "effort".]

--- DESIGN / PROTOTYPE REFERENCE ---
[Link to the prototype/Figma/Artifact, if applicable to this specific story.]

--- NON-FUNCTIONAL REQUIREMENTS (if any) ---
[Only applicable, testable NFRs: security, atomicity, idempotency, backward
compatibility, observability, performance. Never a generic "should be fast/secure".]
```

Pull source material from across the whole PRD, not just Section 6: Section 5 (User Flows) for the step-by-step flow, Section 7 (Features Out) and Section 15 (Technical Notes) for Out of Scope and Validations, Section 11 (Permissions) for the permission scenarios, Section 21 (System Audit Activities) for Logs, Section 13/14 (Security/Handling) for NFRs, and Section 17 (Design) for the prototype reference.

Write every story into one combined file (e.g. `all_stories.txt`), each story starting with its own `--- STORY HEADER ---` marker back to back with no other separator needed; the script splits automatically on that marker in Step 7. Only fall back to one file per story (`story_7.txt`, `story_9.txt`, ...) when fixing or resuming a small number of stories after a partial-run failure, so a fix to one story doesn't require editing inside the shared combined file.

## Step 5: Sequence the Stories

List the final story set in release order and state the real dependency for any ordering that isn't self-evident (e.g. "Story 3 must release before Story 7 because Story 7 produces the Void state that Story 3's detail view must already render safely"). Never sequence by team preference, "backend before frontend" as a generic rule, or story-number aesthetics.

## Step 6: Run the Quality Gates

Read `references/quality-gates.md` and check every story against it before punching anything into Zoho: can it release without exposing incomplete behavior, can it stay live if a later story slips, are permissions/limits/failure behavior all defined, is every resulting state actually usable at the point it's introduced, and (for any story extending an already-live capability) does it prove existing behavior stays unchanged. Fix anything that fails before Step 7, not after.

This step covers what needs judgment (behavioral completeness, correctness). The mechanical parts of the locked format, a three-part STORY ID, every required header field and section present, every scenario numbered, no banned em dash or double hyphen, are checked automatically by the script itself in Step 7 (`lint_story()`), not by re-reading the docs carefully. That automatic check exists specifically because "read the format doc again" has already failed to catch these in a real run: a story rewritten from a prior story's structure can silently drop something the locked template requires, no matter how many times the docs say otherwise. Plain language cannot be checked mechanically; that still depends on this step and on Step 4's instruction to write it plainly the first time.

## Step 7: Run the Script

- **Never use the `claude.ai Zoho Sprint` MCP connector**: it's unauthenticated and is not how this actually works.
- **Real auth mechanism:** each person running this needs their own Zoho OAuth credentials in a `.env` file; see Step 0 above and `scripts/README.md`.
- **Script:** `scripts/create_prd_sprint_item.py` in this repo, with its own copy of `sprint_config.json` alongside it in the same folder. If you also maintain a separate script for bug-item creation elsewhere, keep the two separate; this one is scoped to PRD-to-Sprint story generation only.
- **Every PRD gets its own new sprint, named after the PRD/feature name.** Do not add stories to whatever sprint is currently active.
- **The script lints every story before sending anything to Zoho**, for both creating and updating. A missing TEAM field, a two-part STORY ID, an unnumbered scenario, a missing required section, or a banned em dash all fail the run with a printed list of exactly what's wrong, before any API call happens. Fix the story file and rerun; there is no flag to bypass this.

```bash
python3 create_prd_sprint_item.py --new-sprint "Feature Name" \
    --project collexo-team1 \
    --epic-id <resolved epicId> \
    --stories-file all_stories.txt
```

- **Resuming after a partial failure:** if the script dies partway through (e.g. one story's subject or content triggers a Zoho API error), do not re-run the full command; it would recreate a duplicate sprint and duplicate the stories that already succeeded. Fix the affected story, then resume into the same sprint with `--existing-sprint-id <sprint ID from the earlier output>` and only the remaining story file(s), via `--story-file` for one or two, or a smaller `--stories-file` for several.

- **Owner/assignment defaults**: every item is created with QA Owner, Dev Owner, Assigned To, and Task Type already set. **These defaults live in `sprint_config.json`**, under each project's `"owner_fields"` (which custom field IDs map to which role) and `"owner_defaults"` (which person/option is the default) blocks - that file is the source of truth, not this skill. Do not restate specific field IDs, user IDs, or names here.
  - Override per run with `--qa-owner-id`, `--dev-owner-id`, `--assigned-id` (repeatable), `--task-type-id` if a specific PRD needs different owners than the project's configured defaults.
  - **If the target project has no `owner_defaults` yet** (a brand-new project this skill hasn't been used on before), run `python3 create_prd_sprint_item.py --discover-owner-defaults --project <key>` first. This samples that project's backlog live (no local sync data required) to find the most common QA Owner/Dev Owner/Task Type values and prints a suggested block; confirm the suggestion with the user (the top statistical candidate isn't automatically the right default - e.g. recent activity and all-time volume can disagree) before adding it to that project's `sprint_config.json` entry. Once added, every future PRD for that project uses it automatically.
- **No bypassing:** this step is part of the deliverable, not optional polish. If something doesn't work, say so explicitly and leave it as an open, tracked next action; don't silently skip it or fall back to only writing the stories into the Doc.

## Step 8: Update Existing Stories

Use this instead of Step 7 when the PRD changed after its stories were already punched into Zoho (a new endpoint, a corrected acceptance criterion, a rewritten description), not to create new stories.

- **Every creation run writes an ids file automatically**, `zoho-story-ids.md` by default, in whatever directory the script was run from (override with `--ids-file`). It maps each story's STORY ID label to the Zoho item it became: `item_no`, `item_id`, `sprint_id`, `project`. This file is what makes an update possible; without it there is no reliable way to know which live item a given story maps to.
- **To update, edit the story file(s) and rerun with `--update`** instead of `--new-sprint`/`--existing-sprint-id`:
  ```bash
  python3 create_prd_sprint_item.py --update \
      --project collexo-team1 \
      --stories-file all_stories.txt
  ```
  Each story's `STORY ID:` line is looked up in the ids file to find which item to push the new subject and description onto. **The STORY ID label is the join key, so if it changes (for example, fixing it to the correct three-part format), update the label in the ids file to match** before running `--update`, or the run will fail with "not found in ids file" rather than silently creating a mismatch.
- **A story with no `STORY ID:` line, or a label missing from the ids file, fails the whole run before anything is sent**, listing exactly which label was not found and what labels are known. There is no partial-update fallback; fix the label or the ids file and rerun.
- **This does not touch owners, priority, epic, or type.** Only `name` (the subject) and `description` change. If those other fields need to change too, that is a small, separate addition to `update_item()`'s callers in `main()`, not something to hand-edit in Zoho.

**Status as of 2026-08-25:** `create_sprint()` and `create_item()` both confirmed against the official docs (`sprints.zoho.in/apidoc.html#Createsprint` / `#Createitem`) and live-tested successfully: sprint creation, item creation, title extraction (`subject_from_story()`, which pulls just the "I want [to] ..." action clause, not the full sentence), HTML-formatted descriptions (`format_story_html()`, which bolds headings, adds spacing, and bolds `Scenario N:` sub-lines), and all four owner/assignment fields, all confirmed working in the throwaway sprint "ZZZ_TEST_DELETE_ME: Sprint Script Verification" (ID `39713000007527839`) in `Collexo_Team_1`. The description parser is header-generic (any `--- SECTION ---` line), so the expanded Step 4 story format (2026-08-27) needed no script changes.

**Updated 2026-08-27, live-tested against the Punching of Advance Fees sprint (10 stories, ID `39713000007626059`), items I11677 through I11686:** `subject_from_story()`'s regex required the literal phrase "I want to" and silently fell back to the entire raw statement, including "As a... So that...", for a story phrased "I want X to happen" instead (valid system-actor phrasing); the resulting oversized subject caused a live 500 from Zoho's create-item API mid-run. Fixed by making "to" optional in the regex and adding a 250-character hard cap on every extracted subject regardless of which branch matched. Added `--existing-sprint-id` to resume a partial run into the already-created sprint instead of restarting into a duplicate one. Added `--stories-file` and `split_stories()`, which splits one file into many stories on their `--- STORY HEADER ---` markers, so creating N stories takes one file and one command instead of N files and N `--story-file` flags; verified it splits a 10-story combined file into exactly 10 correctly-titled blocks matching what `--story-file` had already created individually.

---

## Reference files

- `references/slicing-and-sequencing.md`: pre-writing analysis, the slicing method and independence tests, release-order principles, and live-release extension mode. Read before Step 3.
- `references/story-format.md`: section-by-section rules behind the Step 4 template, and the mandatory acceptance-criteria scenario categories. Read while drafting.
- `references/quality-gates.md`: quality gate checklists, common failure patterns, and the definition of done. Read before Step 6.
