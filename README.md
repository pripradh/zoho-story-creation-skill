# Zoho Story Creation Skill

Skill to create granular stories and update the same in the Zoho Sprint via APIs.

A Claude Code skill that turns a finalized PRD into a Zoho Sprints sprint with
implementation-ready stories, created directly via the Zoho Sprints API.

It does not copy a PRD's user stories 1:1 into Sprint items. Instead it runs its
own slicing pass over the whole PRD, splits work at genuine independent-release
boundaries, and writes every story in a single locked format (header, user story
statement, description, acceptance criteria in Given/When/Then, example cases,
validations, logs, out-of-scope, dependencies, non-functional requirements)
before punching anything into Zoho.

## What it does, step by step

1. **Verify the Zoho Sprints connection** — confirms a usable OAuth credential
   exists and actually resolves to an access token, before any analysis starts.
2. **Confirm inputs** — the finalized PRD, the feature name, and the target
   Zoho project.
3. **First-time project setup** (new projects only) — discovers project ID,
   backlog ID, item types, and priorities live from the Zoho API rather than
   asking the user to guess them.
4. **Resolve the epic** — maps the PRD's feature area to an existing epic in
   the target project; never invents a new epic per PRD.
5. **Slice the PRD** into independently releasable stories, based on an
   analysis of actors, triggers, states, permissions, and failure behavior
   pulled from across the whole PRD, not just its user-story section.
6. **Write each story** in the locked format described below.
7. **Sequence the stories** in real dependency order.
8. **Run quality gates** against every story before anything is written.
9. **Run the script** that creates the sprint and punches in every story via
   the Zoho Sprints API, resumable if it fails partway through.

## Story format

Every story is written with:

- A header block: story ID, module/epic, team, priority, story points, feature flag
- A user story statement (As a / I want / So that)
- A description of current behavior, the gap, and the exact new behavior
- Prerequisites and a numbered user/system flow
- Acceptance criteria in Given/When/Then, covering every scenario category that
  materially applies (primary behavior, state transitions, boundary conditions,
  permissions, failure handling, data integrity, regression protection)
- Example cases that ground the acceptance criteria in a concrete instance
- Validations, logs, out-of-scope items, and dependencies
- A design/prototype reference and non-functional requirements

See `references/story-format.md` for the full section-by-section rules,
`references/slicing-and-sequencing.md` for the pre-writing analysis method, and
`references/quality-gates.md` for the definition-of-done checklist run before
anything is created.

## Requirements

- A Zoho Sprints account with API access
- Your own Zoho OAuth credentials (`ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`,
  `ZOHO_REFRESH_TOKEN`, and `ZOHO_DC` if your org isn't on the India
  datacenter), supplied via a `.env` file
- A companion script that talks to the Zoho Sprints API (not included in this
  repo) and a `sprint_config.json` holding your org's project/epic/owner-field
  mappings

## Usage

Invoke once a PRD is written, confirmed, and explicitly signed off, with a
request like "create the sprint stories for X" or "punch this PRD into
Sprints." It refuses to run against a PRD that's still open for edits.

## License

Add a license of your choice before treating this as reusable by others outside
your own workspace.
