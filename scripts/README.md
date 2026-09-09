# create_prd_sprint_item.py

Creates a Zoho Sprints sprint and stories directly via the Sprints API. Used
by the `collexo-prd-sprint` skill to punch a finished PRD's sliced stories
into Zoho Sprints, but the script itself has no dependency on Claude Code and
can be run standalone by anyone with the right Zoho credentials.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt` (just `requests`)

## Get Zoho OAuth credentials

Each person running this script needs their own Zoho self-client credentials.
Do not share a refresh token between people; generate your own.

1. Go to the [Zoho API Console](https://api-console.zoho.com) (or the
   console for your org's datacenter, e.g. `api-console.zoho.in`) and create
   a **Self Client**.
2. Under **Generate Code**, request these scopes at minimum:
   - `ZohoSprints.sprints.CREATE` (create a new sprint)
   - `ZohoSprints.sprints.READ` (look up a sprint by name if the create
     response doesn't return an ID directly)
   - `ZohoSprints.items.CREATE` (create stories inside a sprint)
   - `ZohoSprints.items.READ` (needed if you also want to resolve epic IDs;
     see the `collexo-prd-sprint` skill's notes on the `epics.READ` scope
     gap)
   Confirm the exact scope names against the Sprints API docs at the time
   you generate the client. 🧪 Needs verification if Zoho has changed these.
3. Exchange the generated code for a refresh token (Zoho's standard
   authorization-code grant flow). The refresh token does not expire unless
   revoked.
4. Copy `.env.example` to `.env` in this same folder and fill in
   `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`. Set
   `ZOHO_DC` only if your org's Zoho account is not on the India datacenter.

The script looks for credentials in this order: `--env-file <path>`, then the
`ZOHO_SPRINT_ENV` environment variable, then `.env` in this folder, then
`~/.collexo/sprint-sync/.env` as a last-resort fallback for the original
Collexo setup.

## Config

`sprint_config.json` holds the Zoho project/item-type/priority IDs for the
projects this script knows about (`collexo-team1`, `pixi-team1`, etc.). These
are specific to the Collexo Zoho Sprints team. It's also the source of truth
for the items below - do not duplicate these into docs or prose elsewhere,
since a copy can silently go stale:

- **A brand-new project's `name`/`project_id`/`backlog_id`/`item_types`/`priorities`**:
  fully discoverable live, no manual ID lookup needed. Run:
  ```bash
  python3 create_prd_sprint_item.py --discover-project "<Zoho project display name>"
  ```
  Matches against the team's live project list (prints every project if the
  name doesn't match) and prints a ready-to-paste config block. Still add
  `"defaults"` yourself (which item type/priority to use when none is
  specified - a policy choice, not something an API can answer).

- **`"owner_fields"`**: which custom field IDs hold QA Owner/Dev Owner/Task
  Type, per project. **Not discoverable from any API tested** (confirmed
  2026-08-31: the live form-fields endpoint doesn't expose these internal
  `UDF_*` codes at all) - a new project either shares `collexo-team1`'s
  known layout (ask whoever set up that project's custom fields to confirm)
  or needs its own one-time manual confirmation the same way `collexo-team1`'s
  were originally found (checking one live item against the Zoho UI).

- **`"owner_defaults"`**: who the default person/option is for each
  `owner_field`, per project. Only meaningful once `"owner_fields"` above is
  set. Run:
  ```bash
  python3 create_prd_sprint_item.py --discover-owner-defaults --project <key>
  ```
  This samples that project's backlog live (no local sync data required) and
  prints a suggested block. It only prints; confirm the suggestion, then add
  it to that project's entry in `sprint_config.json` yourself.

- **`"epics"`**: `{epicId: name}` per project. If an epic isn't listed yet:
  ```bash
  python3 create_prd_sprint_item.py --discover-epics --project <key>
  ```
  This finds every epicId in use on that project's backlog with one cheap
  live call, and marks each as already-named or `UNKNOWN`. Zoho's dedicated
  "Get epics" API is blocked on this credential set by a missing OAuth scope
  (confirmed 2026-08-31), so an `UNKNOWN` epic's name can't be fetched
  automatically - open one of the example items the command prints in the
  Zoho Sprints UI, read its Epic field, and add the name to `sprint_config.json`
  yourself. Each epicId only needs naming once, ever, across all future runs.

## Caching

Two things get cached locally in `.zoho_token_cache.json` (gitignored) so
repeated runs don't re-hit the network for the same data:
- the OAuth access token (valid ~1hr; refreshed automatically once stale)
- the per-project user-ID-to-name roster used to label `--discover-owner-defaults`
  output (refreshed automatically after 24h, or sooner if a lookup misses)

Delete this file any time to force a fresh fetch of both.

## Usage

See the script's own `--help`, or the `collexo-prd-sprint` skill's SKILL.md
Step 7, for command examples.
