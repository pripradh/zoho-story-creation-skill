#!/usr/bin/env python3
"""Create a PRD story (or several) in a brand-new Zoho Sprints sprint.

This is a PRD-specific fork of ~/.meritto/Raw Ticket Data/create_sprint_item.py —
that original script is live infrastructure for the ticket-reply skill's bug-item
creation and must never be edited. This copy exists so PRD story creation can
diverge freely: every PRD gets its own new sprint (named after the PRD), and each
story carries the full locked story format in its description, not just a subject.

Usage (preferred: one file holding every story, split automatically):
  python3 create_prd_sprint_item.py --new-sprint "Punching of Advance Fees" \\
      --project collexo-team1 --epic-id 39713000000199255 \\
      --stories-file all_stories.txt

  # Alternative: one file per story, useful when fixing or resuming just one or
  # two stories after a partial-run failure, without touching the others:
  python3 create_prd_sprint_item.py --existing-sprint-id 39713000007626059 \\
      --project collexo-team1 --story-file story_7.txt --story-file story_9.txt

  # Or pass one story inline, no file at all:
  python3 create_prd_sprint_item.py --new-sprint "Punching of Advance Fees" \\
      --project collexo-team1 --subject "Punch an advance payment" \\
      --description-file story_1.txt

Options:
  --new-sprint TEXT       Name for the new sprint, the PRD/feature name. Required unless
                          --existing-sprint-id is used instead.
  --existing-sprint-id ID Resume adding items into an already-created sprint (e.g. after a
                          partial-run failure) instead of creating a new one. Mutually
                          exclusive with --new-sprint.
  --project KEY          Project key from sprint_config.json (default: collexo-team1)
  --sprint-description   Optional description for the new sprint (e.g. link to the PRD Doc)
  --subject TEXT         Item title (required per item; use --story-file or --stories-file
                          for multiple)
  --description-file PATH  File containing the full locked story format for this item's description
  --stories-file PATH     A single file holding multiple stories back to back, each starting
                          with its own "--- STORY HEADER ---" marker. Splits automatically
                          into one Zoho item per story. Preferred over --story-file when
                          creating several stories at once, since it is one file and one flag
                          regardless of story count.
  --story-file PATH       Repeatable. Each file is one story in the locked format; its
                          "I want [to] ..." clause becomes the subject, the whole file becomes
                          the description. Best for fixing or resuming a single story, not for
                          creating many at once (use --stories-file for that).
  --type TEXT             Item type name (default: project default, "Story" for collexo-team1)
  --priority TEXT         Priority name (default: project default)
  --epic-id ID            Optional epic to map every created item to

Project keys:
  collexo-team1     Collexo_Team_1   (PRD stories for Collexo)
  pixi-team1        Pixi_Team_1      (PRD stories for Pixi)
  collexo-bugs      Collexo_Live_Bugs  — do NOT use for PRD stories, bug-tracking only
  bugs-issues       Bugs & Issues      — do NOT use for PRD stories, bug-tracking only
  collexo-roadmap   Collexo Product Roadmap
  pixi-roadmap      Pixi Product Roadmap

Unlike the ticket-reply bug-item script, this one never auto-selects an existing
active sprint — every run creates a fresh sprint via the Zoho Sprints "Create
sprint" API (POST .../projects/{projectId}/sprints/, confirmed against the
official docs at sprints.zoho.in/apidoc.html#Createsprint on 2026-08-25) and adds
every story into that new sprint.

Examples:
  python3 create_prd_sprint_item.py --new-sprint "Punching of Advance Fees" \\
      --project collexo-team1 --stories-file all_stories.txt
"""

import argparse
import json
import re
import sys
from pathlib import Path

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "sprint_config.json"

# Zoho datacenter, e.g. "in" (default), "com", "eu", "au", "jp" - must match the
# DC the Zoho org actually lives in, or token exchange fails. Set ZOHO_DC in the
# .env file to override; see README.md.
DEFAULT_ZOHO_DC = "in"


def urls_for_dc(dc):
    return (
        f"https://accounts.zoho.{dc}/oauth/v2/token",
        f"https://sprintsapi.zoho.{dc}/zsapi/team",
    )

# ── Config ────────────────────────────────────────────────────────────────────

def load_config():
    if not CONFIG_PATH.exists():
        print(f"ERROR: {CONFIG_PATH} not found.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def resolve_project(cfg, key):
    key = cfg["aliases"].get(key, key)
    proj = cfg["projects"].get(key)
    if not proj:
        valid = list(cfg["projects"]) + list(cfg["aliases"])
        print(f"ERROR: unknown project {key!r}. Valid keys: {', '.join(valid)}")
        sys.exit(1)
    return key, proj


def resolve_ids(proj, item_type_label=None, priority_label=None):
    item_type_label = item_type_label or proj["defaults"]["item_type"]
    priority_label  = priority_label  or proj["defaults"]["priority"]

    type_id = proj["item_types"].get(item_type_label)
    prio_id = proj["priorities"].get(priority_label)

    if not type_id:
        valid = list(proj["item_types"])
        print(f"ERROR: item type {item_type_label!r} not found. Valid: {', '.join(valid)}")
        sys.exit(1)
    if not prio_id:
        valid = list(proj["priorities"])
        print(f"ERROR: priority {priority_label!r} not found. Valid: {', '.join(valid)}")
        sys.exit(1)
    return type_id, prio_id


def resolve_owner_config(proj):
    """QA/Dev owner and Task Type are per-project custom fields, only set on
    projects where sprint_config.json declares "owner_fields" - a custom field
    ID confirmed for one project (e.g. collexo-team1's UDF_USERPKL2) is not
    safe to assume for another project's differently-configured layout.
    Returns (fields, defaults), either possibly {} if the project has none."""
    return proj.get("owner_fields", {}), proj.get("owner_defaults", {})

# ── Auth ──────────────────────────────────────────────────────────────────────

# Credential lookup order, so this script works for anyone without editing
# code: an explicit --env-file flag, then the ZOHO_SPRINT_ENV variable, then a
# .env colocated with the script (the normal case for a fresh checkout), then
# the original Collexo sprint-sync location as a last-resort fallback so any
# existing setup keeps working unchanged. See README.md for how to obtain the
# three required keys.

FALLBACK_ENV_PATH = Path.home() / ".collexo" / "sprint-sync" / ".env"


def resolve_env_path(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    import os
    if os.environ.get("ZOHO_SPRINT_ENV"):
        return Path(os.environ["ZOHO_SPRINT_ENV"]).expanduser().resolve()
    local = SCRIPT_DIR / ".env"
    if local.exists():
        return local
    return FALLBACK_ENV_PATH


def parse_env_file(env_path):
    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def load_env(explicit_path=None):
    env_path = resolve_env_path(explicit_path)
    if not env_path.exists():
        print(f"ERROR: no .env file found at {env_path}.")
        print("Copy scripts/.env.example to scripts/.env and fill in your Zoho "
              "OAuth credentials (see README.md), or pass --env-file, or set "
              "ZOHO_SPRINT_ENV. Run with --check-setup to diagnose this.")
        sys.exit(1)
    env = parse_env_file(env_path)
    required = ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        print(f"ERROR: {env_path} is missing required key(s): {', '.join(missing)}")
        sys.exit(1)
    return env


# Standalone connection check, used by --check-setup and by the
# collexo-prd-sprint skill's Step 0 preflight, so a missing or broken
# connection is caught before any slicing or story-writing work happens, not
# discovered only when Step 7 tries to actually punch stories in. Prints its
# own actionable guidance rather than a raw stack trace or a bare API error.

def check_setup(explicit_path=None):
    env_path = resolve_env_path(explicit_path)
    print(f"Checking Zoho Sprints connection (env file: {env_path})")

    if not env_path.exists():
        print("  MISSING: no .env file found.")
        print()
        print("  Setup needed, see scripts/README.md \"Get Zoho OAuth credentials\":")
        print("    1. Create a Zoho self-client and generate ZOHO_CLIENT_ID, "
              "ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN")
        print("    2. cp scripts/.env.example scripts/.env")
        print("    3. Fill in the three values (and ZOHO_DC if not on the India datacenter)")
        return False

    env = parse_env_file(env_path)
    required = ["ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        print(f"  INCOMPLETE: {env_path} is missing: {', '.join(missing)}")
        print("  Fill in the missing key(s); see scripts/README.md.")
        return False

    token_url, _ = urls_for_dc(env.get("ZOHO_DC", DEFAULT_ZOHO_DC))
    try:
        resp = requests.post(token_url, data={
            "refresh_token": env["ZOHO_REFRESH_TOKEN"],
            "client_id":     env["ZOHO_CLIENT_ID"],
            "client_secret": env["ZOHO_CLIENT_SECRET"],
            "grant_type":    "refresh_token",
        }, timeout=30)
        data = resp.json()
    except requests.RequestException as e:
        print(f"  FAILED: could not reach Zoho ({e}).")
        print("  Check network access and that ZOHO_DC matches your org's datacenter.")
        return False

    if "access_token" not in data:
        print(f"  FAILED: token exchange rejected: {data}")
        print("  Check ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN, and ZOHO_DC, "
              "and confirm the refresh token has not been revoked; see scripts/README.md.")
        return False

    print("  OK: credentials found and token exchange succeeded.")
    return True


# Local cache for anything read from Zoho that's expensive or wasteful to
# re-fetch on every invocation: the OAuth access token (valid ~1hr) under
# "tokens", and the per-project user-ID-to-name roster under
# "user_display_by_project" - that roster is where qa_owner_id/dev_owner_id/
# assigned_ids ultimately come from (see discover_owner_defaults), and team
# membership changes far slower than the token does, so it gets a much
# longer TTL. Both share one file so there's a single cache to reason about.
CACHE_PATH              = SCRIPT_DIR / ".zoho_token_cache.json"
TOKEN_EXPIRY_SKEW       = 60            # seconds of safety margin before treating a cached token as expired
USER_DISPLAY_CACHE_TTL  = 24 * 60 * 60  # 1 day; re-fetched sooner if a lookup misses


def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache):
    try:
        CACHE_PATH.write_text(json.dumps(cache))
    except OSError:
        pass  # caching is a speed optimization, not required for correctness


def get_access_token(env, token_url):
    import time
    client_id = env["ZOHO_CLIENT_ID"]
    cache  = _load_cache()
    cached = cache.get("tokens", {}).get(client_id)
    if cached and cached.get("expires_at", 0) > time.time() + TOKEN_EXPIRY_SKEW:
        return cached["access_token"]

    resp = requests.post(token_url, data={
        "refresh_token": env["ZOHO_REFRESH_TOKEN"],
        "client_id":     client_id,
        "client_secret": env["ZOHO_CLIENT_SECRET"],
        "grant_type":    "refresh_token",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        print(f"ERROR: Token refresh failed: {data}")
        sys.exit(1)

    cache.setdefault("tokens", {})[client_id] = {
        "access_token": data["access_token"],
        "expires_at":   time.time() + data.get("expires_in", 3600),
    }
    _save_cache(cache)
    return data["access_token"]


def get_cached_user_display(project_id, max_age=USER_DISPLAY_CACHE_TTL):
    """Returns the last-cached user roster for this project if still fresh,
    else {}. Callers merge in anything freshly fetched and call
    update_user_display_cache() to persist it."""
    import time
    entry = _load_cache().get("user_display_by_project", {}).get(project_id)
    if entry and (time.time() - entry.get("fetched_at", 0)) < max_age:
        return entry.get("data", {})
    return {}


def update_user_display_cache(project_id, user_display):
    """Merges freshly-seen id->name pairs into the persisted roster for this
    project (never drops previously-seen names just because this run's
    sample didn't happen to touch them) and refreshes the cache timestamp."""
    import time
    if not user_display:
        return
    cache = _load_cache()
    by_project = cache.setdefault("user_display_by_project", {})
    existing = by_project.get(project_id, {}).get("data", {})
    merged = {**existing, **user_display}
    by_project[project_id] = {"fetched_at": time.time(), "data": merged}
    _save_cache(cache)


def api_headers(token):
    return {
        "Authorization":      f"Zoho-oauthtoken {token}",
        "x-za-ui-version":    "v2",
        "X-convert-response": "true",
    }

# ── First-time project setup: discover owner fields/defaults ──────────────────
# QA Owner (UDF_USERPKL2), Dev Owner (UDF_USERPKL3), and Task Type (UDF_PKL4)
# are confirmed shared field keys across every "planned-release"-family Zoho
# Sprints project (Collexo_Team_1 and Pixi_Team_1 both), per Meritto's own
# sprint-sync job's UDF_PLANNED_RELEASE map (~/.collexo/sprint-sync/sync.py) -
# that map is keyed by dataset type, not by individual project, so the field
# keys are a project-family constant, not something to re-derive per project.
# What is genuinely project-specific is *who* the default people are, which
# this discovers live, entirely through the Zoho API - no dependency on any
# local sync job's output, since that data won't exist on another machine.

PLANNED_RELEASE_OWNER_FIELDS = {
    "qa_owner":  "UDF_USERPKL2",
    "dev_owner": "UDF_USERPKL3",
    "task_type": "UDF_PKL4",
}

# Cap on how many backlog items get a live per-item detail call. The bulk
# list endpoint (action=data) does NOT return custom field values at all -
# confirmed 2026-08-31 live: its item_prop carries only standard fields, no
# UDF_* keys - so reading QA Owner/Dev Owner/Task Type requires one detail
# call (action=details) per item. This cap bounds that cost for a first-time
# setup scan; raise it with --discover-sample-size if a small backlog gives
# too few populated samples to trust a "most common" pick.
DEFAULT_DISCOVERY_SAMPLE_SIZE = 30


# ── First-time project setup: discover the project itself ─────────────────────
# Everything a new sprint_config.json project block needs except owner_fields
# (see the module-level note near PLANNED_RELEASE_OWNER_FIELDS - genuinely not
# exposed by any field-metadata API tested, confirmed 2026-08-31), defaults
# (a policy choice, not Zoho data), and owner_defaults/epics (their own
# discovery commands, since they need a live backlog to sample) is fetchable
# from three cheap live calls: the team's project list, and that project's
# item types and priorities. No local sync data, no per-item calls needed.

def fetch_live_projects(token, base_url):
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2", "X-convert-response": "true"}
    resp = requests.get(f"{base_url}/projects/", headers=headers, params={"action": "data"}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("projects", [])


def fetch_item_types_live(token, project_id, base_url):
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2", "X-convert-response": "true"}
    resp = requests.get(f"{base_url}/projects/{project_id}/itemtype/", headers=headers, params={"action": "data"}, timeout=30)
    resp.raise_for_status()
    return {t["itemTypeName"]: t["projItemTypeId"] for t in resp.json().get("projItemTypes", []) if t.get("projItemTypeId")}


def fetch_priorities_live(token, project_id, base_url):
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2", "X-convert-response": "true"}
    resp = requests.get(f"{base_url}/projects/{project_id}/priority/", headers=headers, params={"action": "data"}, timeout=30)
    resp.raise_for_status()
    return {p["priorityName"]: p["projPriorityId"] for p in resp.json().get("projPriorities", []) if p.get("projPriorityId")}


def discover_project(token, base_url, name_query):
    """Find a Zoho Sprints project by its display name (case-insensitive
    exact match, falling back to substring match) and print a ready-to-paste
    sprint_config.json block: name, project_id, backlog_id, item_types,
    priorities. Never writes anything itself. Still needed after this:
    "defaults" (pick an item_type/priority policy - a human call), and
    owner_fields/owner_defaults/epics via their own discover commands."""
    projects = fetch_live_projects(token, base_url)
    query = name_query.strip().lower()
    matches = [p for p in projects if p.get("projName", "").strip().lower() == query]
    if not matches:
        matches = [p for p in projects if query in p.get("projName", "").lower()]

    if not matches:
        print(f"No Zoho project found matching {name_query!r}. Available projects:")
        for p in sorted(projects, key=lambda p: p.get("projName", "")):
            print(f"  {p.get('projName')}  (id: {p.get('projectId')})")
        return None
    if len(matches) > 1:
        print(f"{len(matches)} projects match {name_query!r} - re-run with the exact name:")
        for p in matches:
            print(f"  {p.get('projName')}  (id: {p.get('projectId')})")
        return None

    match      = matches[0]
    project_id = match["projectId"]
    backlog_id = match.get("backlogId")
    name       = match.get("projName")
    print(f"Matched: {name}  (project_id: {project_id}, backlog_id: {backlog_id})\n")

    item_types = fetch_item_types_live(token, project_id, base_url)
    priorities = fetch_priorities_live(token, project_id, base_url)

    print("Item types:")
    for tname, tid in item_types.items():
        print(f"  {tname}: {tid}")
    print("\nPriorities:")
    for pname, pid in priorities.items():
        print(f"  {pname}: {pid}")

    block = {
        "name":        name,
        "project_id":  project_id,
        "backlog_id":  backlog_id,
        "item_types":  item_types,
        "priorities":  priorities,
    }
    print("\nSuggested sprint_config.json block (add \"defaults\" yourself - pick which item "
          "type/priority this script should use when none is specified - then run "
          "--discover-owner-defaults and --discover-epics once this block is saved):")
    print(json.dumps(block, indent=2))
    return block


def fetch_backlog_item_ids(token, project_id, backlog_id, base_url):
    """The bulk list endpoint is cheap and returns itemIds + a user-display
    roster (id->name for everyone referenced on the project), but not custom
    field values - see the module note above."""
    url = f"{base_url}/projects/{project_id}/sprints/{backlog_id}/item/"
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2"}
    resp = requests.get(url, headers=headers, params={"action": "data", "index": 1, "range": 100}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("itemIds", []), data.get("userDisplayName", {})


def fetch_epic_usage(token, project_id, backlog_id, base_url):
    """One cheap bulk call - epicId is a standard item field (unlike custom
    UDF_* fields), so it's already populated in the bulk list response and
    needs no per-item detail calls. Returns {epicId: example_item_name} for
    every distinct epicId currently in use on this project's backlog.

    This only gives numeric IDs, not names: Zoho's dedicated "Get epics" API
    (GET .../projects/{projectId}/epic/) is blocked on this credential set
    with a 401 "Invalid oauthscope" (confirmed live 2026-08-31, matching this
    skill's SKILL.md Step 2 note from 2026-08-25) - fixing that for good
    requires adding the missing scope to the Zoho self-client and
    regenerating the refresh token, not something discoverable at runtime."""
    url = f"{base_url}/projects/{project_id}/sprints/{backlog_id}/item/"
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2"}
    resp = requests.get(url, headers=headers, params={"action": "data", "index": 1, "range": 100}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    item_prop = data.get("item_prop", {})
    epic_idx  = item_prop.get("epicId")
    name_idx  = item_prop.get("itemName")
    if epic_idx is None:
        return {}

    usage = {}
    for item_id in data.get("itemIds", []):
        arr = data.get("itemJObj", {}).get(item_id)
        if not arr or epic_idx >= len(arr):
            continue
        val = arr[epic_idx]
        if val in (None, "", "-1"):
            continue
        if val not in usage:
            usage[val] = arr[name_idx] if name_idx is not None and name_idx < len(arr) else item_id
    return usage


def discover_epics(token, project_id, backlog_id, base_url, known_epics):
    """First-time (or ongoing) project setup: find every epicId actually in
    use on this project's backlog, live, and cross-reference against
    known_epics (this project's already-named epics from sprint_config.json).
    Prints which are already known and which are new and need a human to
    name them once (see fetch_epic_usage's docstring for why naming can't be
    automated). Never writes anything itself."""
    usage = fetch_epic_usage(token, project_id, backlog_id, base_url)
    if not usage:
        print("No epic usage found in this project's backlog.")
        return

    print(f"Found {len(usage)} distinct epic(s) in use on this project's backlog:\n")
    unresolved = {}
    for epic_id, example in usage.items():
        name = known_epics.get(epic_id)
        if name:
            print(f"  {epic_id}  {name}")
        else:
            print(f"  {epic_id}  UNKNOWN  - e.g. item: {str(example)[:70]}")
            unresolved[epic_id] = example

    if unresolved:
        print(f"\n{len(unresolved)} epic(s) above are not yet named in sprint_config.json.")
        print("Open one example item per UNKNOWN epicId in the Zoho Sprints UI and read its "
              "Epic field, then add the name to this project's \"epics\" block in "
              "sprint_config.json, e.g.:")
        print('  "epics": {"' + next(iter(unresolved)) + '": "<real epic name>"}')
        print("Once added, every future run recognizes it automatically - each epicId only "
              "needs naming once.")
    else:
        print("\nAll epics in use are already named in sprint_config.json.")


def fetch_item_owner_fields(token, project_id, backlog_id, item_id, base_url, owner_fields):
    """One live per-item detail call, decoded via item_prop (field name ->
    array index) and itemJObj (item_id -> value array), the same raw-response
    scheme SKILL.md documents for epic-ID resolution. Returns {role: raw_value}
    for whichever of owner_fields had a non-empty value on this item."""
    url = f"{base_url}/projects/{project_id}/sprints/{backlog_id}/item/{item_id}/"
    headers = {"Authorization": f"Zoho-oauthtoken {token}", "x-za-ui-version": "v2"}
    resp = requests.get(url, headers=headers, params={"action": "details"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    item_prop = data.get("item_prop", {})
    arr = data.get("itemJObj", {}).get(item_id)
    if not arr:
        return {}, data.get("userDisplayName", {})
    found = {}
    for role, field_key in owner_fields.items():
        idx = item_prop.get(field_key)
        if idx is None or idx >= len(arr):
            continue
        val = arr[idx]
        if val not in (None, "", "-1"):
            found[role] = val
    return found, data.get("userDisplayName", {})


def discover_owner_defaults(token, project_id, backlog_id, base_url, owner_fields,
                             sample_size=DEFAULT_DISCOVERY_SAMPLE_SIZE):
    """First-time project setup: sample this project's backlog live (no local
    sync data required) to find the most common QA Owner / Dev Owner / Task
    Type values, then resolve the winning IDs to names for a human to
    confirm. Prints ranked candidates and a suggested sprint_config.json
    block; never writes anything itself, since picking the right default is
    a human call, not a purely statistical one."""
    from collections import Counter

    # Seed from the cached roster (see get_cached_user_display) so a name
    # resolved in a previous run doesn't require hitting the network again;
    # everything freshly seen this run still gets merged in and persisted
    # below, so the cache only grows more complete over time.
    user_display = dict(get_cached_user_display(project_id))

    item_ids, live_display = fetch_backlog_item_ids(token, project_id, backlog_id, base_url)
    user_display.update(live_display)
    if not item_ids:
        print("This project's backlog has no items to sample. Add owner_defaults manually, "
              "or run this again once the backlog has some history.")
        return {}

    sample = item_ids[:sample_size]
    print(f"Backlog has {len(item_ids)} item(s); sampling {len(sample)} via live detail calls "
          f"(one call per item)...")

    counters = {role: Counter() for role in owner_fields}
    for i, item_id in enumerate(sample, 1):
        found, extra_display = fetch_item_owner_fields(token, project_id, backlog_id, item_id, base_url, owner_fields)
        user_display.update(extra_display)
        for role, val in found.items():
            counters[role][val] += 1
        if i % 10 == 0:
            print(f"  ...{i}/{len(sample)}")

    update_user_display_cache(project_id, user_display)
    print(f"Done. Scanned {len(sample)} item(s).\n")
    if not any(counters.values()):
        print("No populated qa_owner/dev_owner/task_type values found in the sample. "
              "Try a larger --discover-sample-size, or set owner_defaults manually.")
        return {}

    suggestions = {}
    for role, counter in counters.items():
        if not counter:
            print(f"  {role}: no populated values found in the sample.")
            continue
        print(f"  {role} candidates:")
        for val, count in counter.most_common(5):
            label = user_display.get(val, "(name not in this sample's roster)")
            print(f"    {val}  {label}  - seen {count} time(s)")
        suggestions[role] = counter.most_common(1)[0][0]
        print()

    if suggestions:
        print("Suggested owner_defaults (top candidate per field, confirm before using):")
        block = {
            "qa_owner_id":  suggestions.get("qa_owner"),
            "dev_owner_id": suggestions.get("dev_owner"),
            "assigned_ids": [suggestions.get("dev_owner")] if suggestions.get("dev_owner") else [],
            "task_type_id": suggestions.get("task_type"),
        }
        print(json.dumps(block, indent=2))
    return suggestions

# ── Sprint lookup / creation ──────────────────────────────────────────────────
# "Create sprint" confirmed 2026-08-25 against the official docs at
# sprints.zoho.in/apidoc.html#Createsprint: POST .../projects/{projectId}/sprints/,
# form-encoded, scope ZohoSprints.sprints.CREATE. name is the only mandatory field.
# The doc's own example response for this endpoint only showed permission_prop /
# permissionJObj / status — no sprintId — which looks like a copy-paste from a
# different endpoint's example rather than this one's real shape. So this function
# does NOT trust a single expected key: it tries the plausible ID keys first, and
# if none are present, falls back to fetching the sprint list and matching by the
# exact name just created (most-recently-created match). Confirm this actually
# works against a real (throwaway) sprint before relying on it for a real PRD.

def fetch_sprints(token, project_id, base_url):
    url  = f"{base_url}/projects/{project_id}/sprints/"
    hdrs = api_headers(token)
    all_sprints, index = [], 1
    while True:
        resp = requests.get(url, headers=hdrs,
            params={"action": "data", "type": "[1,2,3,4]", "index": index, "range": 100}, timeout=30)
        resp.raise_for_status()
        data  = resp.json()
        batch = data.get("sprints", [])
        all_sprints.extend(batch)
        if not data.get("next") or not batch:
            break
        index += 100
    return all_sprints


def create_sprint(token, project_id, base_url, name, description=None, startdate=None,
                   enddate=None, duration=None, scrummaster=None, users=None):
    url  = f"{base_url}/projects/{project_id}/sprints/"
    data = {"name": name}
    if description:
        data["description"] = description
    if startdate:
        data["startdate"] = startdate
    if enddate:
        data["enddate"] = enddate
    if duration:
        data["duration"] = duration
    if scrummaster:
        data["scrummaster"] = str(scrummaster)
    if users:
        data["users"] = json.dumps(users)

    resp = requests.post(url, headers={"Authorization": f"Zoho-oauthtoken {token}"}, data=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("status") not in (None, "success"):
        print(f"ERROR creating sprint: {result}")
        sys.exit(1)

    for key in ("sprintId", "addedSprintId", "id"):
        if result.get(key):
            return str(result[key])

    # Fallback: the create response didn't carry an obvious ID — look it up by name.
    print("  (create-sprint response had no obvious sprint ID — looking it up by name...)")
    sprints = fetch_sprints(token, project_id, base_url)
    matches = [s for s in sprints if s.get("sprintName", "").strip() == name.strip()]
    if not matches:
        print(f"ERROR: sprint '{name}' was not found after creation. Raw create response: {result}")
        sys.exit(1)
    if len(matches) > 1:
        print(f"  WARNING: {len(matches)} sprints named '{name}' exist — using the last one returned. "
              f"Check for duplicates from a previous failed/retried run.")
    return matches[-1]["sprintId"]

# ── Create item ───────────────────────────────────────────────────────────────
# "Create item" confirmed 2026-08-25 against sprints.zoho.in/apidoc.html#Createitem.
# description is a real, documented field (String — "Detailed description of the
# item"); this is where the full locked PRD story format goes. epicid is also real
# and optional, for mapping every story under one epic per PRD if desired.

def create_item(token, project_id, sprint_id, name, type_id, priority_id, base_url,
                 task_id=None, description=None, epic_id=None,
                 qa_owner_id=None, qa_owner_field=None,
                 dev_owner_id=None, dev_owner_field=None,
                 task_type_id=None, task_type_field=None,
                 assigned_ids=None):
    # qa_owner_field/dev_owner_field/task_type_field are per-project custom
    # field IDs (e.g. "UDF_USERPKL2"), resolved from that project's
    # "owner_fields" block in sprint_config.json, not hardcoded here - a
    # custom field ID confirmed for one project is not safe to reuse on
    # another project's differently-configured layout.
    url  = f"{base_url}/projects/{project_id}/sprints/{sprint_id}/item/"
    data = {
        "name":           name,
        "projitemtypeid": str(type_id),
        "projpriorityid": str(priority_id),
    }
    if task_id:
        data["UDF_CHAR1"] = str(task_id)
    if description:
        data["description"] = description
    if epic_id:
        data["epicid"] = str(epic_id)
    if qa_owner_id and qa_owner_field:
        data[qa_owner_field] = str(qa_owner_id)
    if dev_owner_id and dev_owner_field:
        data[dev_owner_field] = str(dev_owner_id)
    if task_type_id and task_type_field:
        data[task_type_field] = str(task_type_id)
    if assigned_ids:
        data["users"] = json.dumps(assigned_ids)

    resp = requests.post(url, headers={"Authorization": f"Zoho-oauthtoken {token}"}, data=data, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("status") != "success":
        print(f"ERROR: {result}")
        sys.exit(1)
    return result

# ── Story file parsing ────────────────────────────────────────────────────────
# A --story-file is expected to already be in the locked story format (see
# SKILL.md Step 5). The subject/name for the Sprint item is the short action
# clause from "I want to ..." (not the full "As a / so that" sentence — a full
# run-on sentence is unusable as a Sprint board title). The full text is
# reformatted to HTML for the description field (see format_story_html below),
# since Zoho's description field is rich text and plain "---"-delimited text
# renders as one unbroken block otherwise.

def subject_from_story(text):
    m = re.search(r"USER STORY STATEMENT\s*-*\s*\n(.*?)(?:\n\s*-{2,}|\Z)", text, re.S)
    block = m.group(1).strip() if m else text.strip()
    normalized = " ".join(line.strip() for line in block.splitlines() if line.strip())

    # "to" is optional here on purpose: a story statement written as "I want X to
    # happen" (system-actor phrasing) is just as valid as "I want to do X", and an
    # unmatched literal "I want to" used to silently fall back to the ENTIRE
    # statement (including "As a ... So that ...") as the subject, which can exceed
    # Zoho's item-name length limit and fail the create-item call with a 500.
    action_m = re.search(r"I want\s+(?:to\s+)?(.*?)(?:,?\s+so that\b|[.]\s*$|$)", normalized, re.I)
    action = (action_m.group(1) if action_m else normalized).strip().rstrip(",.")
    if not action:
        return "Untitled story"
    subject = action[0].upper() + action[1:]
    # Hard safety cap regardless of which branch matched, since Zoho's item name
    # field has a length limit and a truncated-but-created subject beats a 500.
    return subject if len(subject) <= 250 else subject[:247].rstrip() + "..."

# ── Multi-story file splitting ─────────────────────────────────────────────────
# A --stories-file holds many stories in one file instead of one file per story.
# Each story already starts with its own "--- STORY HEADER ---" marker (the fixed
# first section of the locked format), so that marker is the natural, unambiguous
# boundary: no extra delimiter syntax to invent or get wrong.

_STORY_HEADER_RE = re.compile(r"^-{2,}\s*STORY HEADER\s*-{2,}\s*$", re.M)

def split_stories(text):
    starts = [m.start() for m in _STORY_HEADER_RE.finditer(text)]
    if not starts:
        # No marker found: treat the whole file as one story, for backward
        # compatibility with a single-story file that omits STORY HEADER.
        return [text.strip()] if text.strip() else []
    starts.append(len(text))
    blocks = [text[starts[i]:starts[i + 1]].strip() for i in range(len(starts) - 1)]
    return [b for b in blocks if b]

# ── Description formatting ────────────────────────────────────────────────────
# Zoho's item description is rich text (HTML), not plain text — sending the raw
# "--- SECTION ---" plain-text block renders as one unbroken wall of text with
# no bold headings and no line spacing. This converts the locked format into
# HTML: bold section headings with blank-line spacing after them and between
# sections, normal body text with line breaks preserved, and "Scenario N: ..."
# sub-lines (inside Acceptance Criteria) bolded too since they're sub-headings.

def _html_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

_SCENARIO_RE = re.compile(r"^Scenario\s+\d+\s*:.*$")
_HEADER_RE   = re.compile(r"^-{2,}\s*(.+?)\s*-{2,}\s*$", re.M)

def _html_body(text):
    lines = [l.strip() for l in text.strip().splitlines()]
    out = []
    for l in lines:
        if not l:
            out.append("")
            continue
        esc = _html_escape(l)
        if _SCENARIO_RE.match(l):
            esc = f"<b>{esc}</b>"
        out.append(esc)
    return "<br>".join(out)

def format_story_html(text):
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return _html_body(text)
    chunks = []
    preamble = text[:matches[0].start()].strip()
    if preamble:
        chunks.append(_html_body(preamble) + "<br><br>")
    for idx, m in enumerate(matches):
        heading = _html_escape(m.group(1).strip())
        start = m.end()
        end   = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body  = text[start:end].strip()
        chunks.append(f"<b>{heading}</b><br><br>{_html_body(body)}<br><br>")
    return "".join(chunks)

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create a new sprint for a PRD, and one or more stories inside it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--new-sprint",  dest="new_sprint", help="Name for the new sprint (the PRD/feature name)")
    parser.add_argument("--existing-sprint-id", dest="existing_sprint_id",
                         help="Resume adding items into an already-created sprint (e.g. after a partial-run "
                              "failure) instead of creating a new one. Mutually exclusive with --new-sprint.")
    parser.add_argument("--sprint-description", dest="sprint_description", help="Optional description for the new sprint")
    parser.add_argument("--project",     default="collexo-team1", help="Project key (default: collexo-team1)")
    parser.add_argument("--subject",     help="Single item title (alternative to --story-file)")
    parser.add_argument("--description-file", dest="description_file", help="File with description text for --subject")
    parser.add_argument("--story-file",  dest="story_files", action="append", default=[],
                         help="Repeatable. Each file is one story in the locked format; subject is derived from it.")
    parser.add_argument("--stories-file", dest="stories_file",
                         help="A single file holding multiple stories back to back, each starting with its own "
                              "'--- STORY HEADER ---' marker. Splits automatically into one Zoho item per story. "
                              "Preferred over many --story-file flags when creating several stories at once.")
    parser.add_argument("--type",        dest="item_type", help="Item type name (default: project default, 'Story' for team projects)")
    parser.add_argument("--priority",    dest="priority",  help="Priority name (default: project default)")
    parser.add_argument("--epic-id",     dest="epic_id",   help="Optional epic ID to map every created item to")
    parser.add_argument("--qa-owner-id",  dest="qa_owner_id",  default=None,
                         help="QA Owner user ID (default: the target project's owner_defaults "
                              "in sprint_config.json, if any)")
    parser.add_argument("--dev-owner-id", dest="dev_owner_id", default=None,
                         help="Dev Owner user ID (default: the target project's owner_defaults "
                              "in sprint_config.json, if any)")
    parser.add_argument("--assigned-id",  dest="assigned_ids", action="append",
                         help="Assigned To user ID (repeatable; default: the target project's "
                              "owner_defaults in sprint_config.json, if any)")
    parser.add_argument("--task-type-id", dest="task_type_id", default=None,
                         help="Task Type picklist option ID (default: the target project's "
                              "owner_defaults in sprint_config.json, if any)")
    parser.add_argument("--env-file", dest="env_file",
                         help="Path to the .env file holding ZOHO_CLIENT_ID/ZOHO_CLIENT_SECRET/"
                              "ZOHO_REFRESH_TOKEN. Default: ZOHO_SPRINT_ENV env var, then "
                              "scripts/.env, then ~/.collexo/sprint-sync/.env.")
    parser.add_argument("--check-setup", action="store_true", dest="check_setup",
                         help="Verify Zoho credentials are configured and that token exchange "
                              "works, then exit. Creates nothing.")
    parser.add_argument("--discover-owner-defaults", action="store_true", dest="discover_owner_defaults",
                         help="First-time project setup: sample --project's backlog live for the "
                              "most common QA Owner/Dev Owner/Task Type values and print a "
                              "suggested owner_defaults block for sprint_config.json. Creates "
                              "nothing. No local sync data required.")
    parser.add_argument("--discover-sample-size", dest="discover_sample_size", type=int,
                         default=DEFAULT_DISCOVERY_SAMPLE_SIZE,
                         help=f"How many backlog items to sample for --discover-owner-defaults "
                              f"(default: {DEFAULT_DISCOVERY_SAMPLE_SIZE}). Each sampled item is "
                              f"one live API call.")
    parser.add_argument("--discover-epics", action="store_true", dest="discover_epics",
                         help="Find every epicId in use on --project's backlog (one cheap live "
                              "call), cross-referenced against this project's already-named "
                              "epics in sprint_config.json. Creates nothing.")
    parser.add_argument("--discover-project", dest="discover_project_name",
                         help="First-time setup for a project not yet in sprint_config.json: "
                              "pass the Zoho project's display name (e.g. \"Collexo_Team_1\") "
                              "to fetch its project_id/backlog_id/item_types/priorities live "
                              "and print a ready-to-paste config block. Creates nothing.")
    args = parser.parse_args()

    if args.check_setup:
        sys.exit(0 if check_setup(args.env_file) else 1)

    if args.discover_owner_defaults:
        cfg = load_config()
        proj_key, proj = resolve_project(cfg, args.project)
        if not proj.get("backlog_id"):
            print(f"ERROR: {proj_key!r} has no backlog_id in sprint_config.json.")
            sys.exit(1)
        owner_fields = proj.get("owner_fields") or PLANNED_RELEASE_OWNER_FIELDS
        if not proj.get("owner_fields"):
            print(f"No owner_fields confirmed yet for {proj_key!r}; assuming the shared "
                  f"planned-release field keys (qa_owner={owner_fields['qa_owner']}, "
                  f"dev_owner={owner_fields['dev_owner']}, task_type={owner_fields['task_type']}). "
                  f"Confirmed shared across collexo-team1 and pixi-team1 by the sprint-sync job's "
                  f"own UDF_PLANNED_RELEASE map; re-verify before trusting this on a project "
                  f"outside that family.\n")
        env = load_env(args.env_file)
        token_url, sprint_api = urls_for_dc(env.get("ZOHO_DC", DEFAULT_ZOHO_DC))
        base_url = f"{sprint_api}/{cfg['team_id']}"
        token = get_access_token(env, token_url)
        discover_owner_defaults(token, proj["project_id"], proj["backlog_id"], base_url,
                                 owner_fields, sample_size=args.discover_sample_size)
        sys.exit(0)

    if args.discover_epics:
        cfg = load_config()
        proj_key, proj = resolve_project(cfg, args.project)
        if not proj.get("backlog_id"):
            print(f"ERROR: {proj_key!r} has no backlog_id in sprint_config.json.")
            sys.exit(1)
        env = load_env(args.env_file)
        token_url, sprint_api = urls_for_dc(env.get("ZOHO_DC", DEFAULT_ZOHO_DC))
        base_url = f"{sprint_api}/{cfg['team_id']}"
        token = get_access_token(env, token_url)
        discover_epics(token, proj["project_id"], proj["backlog_id"], base_url,
                        proj.get("epics", {}))
        sys.exit(0)

    if args.discover_project_name:
        cfg = load_config()
        env = load_env(args.env_file)
        token_url, sprint_api = urls_for_dc(env.get("ZOHO_DC", DEFAULT_ZOHO_DC))
        base_url = f"{sprint_api}/{cfg['team_id']}"
        token = get_access_token(env, token_url)
        discover_project(token, base_url, args.discover_project_name)
        sys.exit(0)

    if not args.subject and not args.story_files and not args.stories_file:
        print("ERROR: pass --subject (with optional --description-file), one or more --story-file, "
              "or --stories-file.")
        sys.exit(1)
    if not args.new_sprint and not args.existing_sprint_id:
        print("ERROR: pass either --new-sprint (to create a fresh sprint) or --existing-sprint-id (to resume one).")
        sys.exit(1)
    if args.new_sprint and args.existing_sprint_id:
        print("ERROR: --new-sprint and --existing-sprint-id are mutually exclusive.")
        sys.exit(1)

    cfg      = load_config()
    proj_key, proj = resolve_project(cfg, args.project)
    if proj_key in ("collexo-bugs", "bugs-issues"):
        print(f"ERROR: '{proj_key}' is a bug-tracking project — PRD stories must not go there. "
              f"Use collexo-team1 or pixi-team1.")
        sys.exit(1)
    type_id, prio_id = resolve_ids(proj, args.item_type, args.priority)

    env = load_env(args.env_file)
    token_url, sprint_api = urls_for_dc(env.get("ZOHO_DC", DEFAULT_ZOHO_DC))
    base_url = f"{sprint_api}/{cfg['team_id']}"
    token = get_access_token(env, token_url)

    print()
    print("=" * 56)
    if args.existing_sprint_id:
        print("  Resuming Existing Sprint")
        print("=" * 56)
        print(f"  Project:    {proj['name']}")
        print(f"  Sprint ID:  {args.existing_sprint_id}")
        print("=" * 56)
        sprint_id = args.existing_sprint_id
        print(f"  Adding items into sprint (ID: {sprint_id})\n")
    else:
        print("  New Sprint")
        print("=" * 56)
        print(f"  Project:    {proj['name']}")
        print(f"  Sprint:     {args.new_sprint}")
        print("=" * 56)
        sprint_id = create_sprint(token, proj["project_id"], base_url, args.new_sprint,
                                   description=args.sprint_description)
        print(f"  Created sprint (ID: {sprint_id})\n")

    # Build the (subject, description) pairs to create. Descriptions always go
    # through format_story_html — Zoho's description field is rich text, so the
    # raw "---"-delimited plain text would render as one unbroken block.
    items = []
    if args.subject:
        desc = format_story_html(Path(args.description_file).read_text()) if args.description_file else None
        items.append((args.subject, desc))
    for path in args.story_files:
        text = Path(path).read_text()
        items.append((subject_from_story(text), format_story_html(text)))
    if args.stories_file:
        blocks = split_stories(Path(args.stories_file).read_text())
        if not blocks:
            print(f"ERROR: no stories found in {args.stories_file} "
                  f"(looked for '--- STORY HEADER ---' markers).")
            sys.exit(1)
        for block in blocks:
            items.append((subject_from_story(block), format_story_html(block)))

    item_type_label = args.item_type or proj["defaults"]["item_type"]
    priority_label  = args.priority  or proj["defaults"]["priority"]

    owner_fields, owner_defaults = resolve_owner_config(proj)
    qa_owner_id   = args.qa_owner_id  or owner_defaults.get("qa_owner_id")
    dev_owner_id  = args.dev_owner_id or owner_defaults.get("dev_owner_id")
    task_type_id  = args.task_type_id or owner_defaults.get("task_type_id")
    assigned_ids  = args.assigned_ids or owner_defaults.get("assigned_ids") or []

    # An ID with no known field for this project can't be sent at all (we'd be
    # guessing a custom field name), so warn once up front rather than
    # silently dropping it per item.
    if qa_owner_id and not owner_fields.get("qa_owner"):
        print(f"  WARNING: QA Owner ID given but {proj_key!r} has no 'owner_fields.qa_owner' "
              f"in sprint_config.json - QA Owner will not be set.")
    if dev_owner_id and not owner_fields.get("dev_owner"):
        print(f"  WARNING: Dev Owner ID given but {proj_key!r} has no 'owner_fields.dev_owner' "
              f"in sprint_config.json - Dev Owner will not be set.")
    if task_type_id and not owner_fields.get("task_type"):
        print(f"  WARNING: Task Type ID given but {proj_key!r} has no 'owner_fields.task_type' "
              f"in sprint_config.json - Task Type will not be set.")

    for subject, description in items:
        print("-" * 56)
        print(f"  Subject:    {subject}")
        print(f"  Type:       {item_type_label}  (ID: {type_id})")
        print(f"  Priority:   {priority_label}  (ID: {prio_id})")
        print(f"  QA Owner:   {qa_owner_id or '(not set, no default for this project)'}")
        print(f"  Dev Owner:  {dev_owner_id or '(not set, no default for this project)'}")
        print(f"  Assigned:   {assigned_ids or '(not set, no default for this project)'}")
        print(f"  Task Type:  {task_type_id or '(not set, no default for this project)'}")
        result  = create_item(token, proj["project_id"], sprint_id, subject, type_id, prio_id, base_url,
                               description=description, epic_id=args.epic_id,
                               qa_owner_id=qa_owner_id, qa_owner_field=owner_fields.get("qa_owner"),
                               dev_owner_id=dev_owner_id, dev_owner_field=owner_fields.get("dev_owner"),
                               task_type_id=task_type_id, task_type_field=owner_fields.get("task_type"),
                               assigned_ids=assigned_ids)
        item_no = result.get("itemNo", "?")
        item_id = result.get("addedItemId", "?")
        print(f"  Created: {item_no}  (internal ID: {item_id})")
    print("-" * 56)
    print()


if __name__ == "__main__":
    main()
