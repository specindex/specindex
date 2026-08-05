#!/usr/bin/env python3
"""Shared project identity: slug IDs, deduplication, and merge helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

ID_MAX = 80

# Layer/catalog URLs shared by every record from a feed are not duplicate keys.
GENERIC_SOURCE_URL = re.compile(
    r"(?i)(/MapServer/\d+/?$|/FeatureServer/\d+/?$|/FeatureServer/?$|/MapServer/?$|"
    r"/Cap/CapHome\.aspx|/Welcome\.aspx|/Submissions\.aspx|/opendata\.arcgis\.com/)"
)

MUNI_ID_PREFIXES = (
    "ga-alpharetta-",
    "ga-johnscreek-",
    "ga-marietta-",
    "ga-atlanta-",
    "ga-gwinnett-",
    "ga-cobb-",
    "ga-fulton-",
    "ga-savannah-",
    "ga-forsyth-",
    "nc-durham-",
    "nc-mecklenburg-",
    "nc-wake-",
    "az-maricopa-",
    "tx-tarrant-",
    "tx-fortworth-",
    "co-denver-",
    "tn-davidson-",
    "tn-nashville-",
    "ct-hartford-",
    "vt-burlington-",
    "ri-providence-",
    "de-statewide-",
    "ks-overlandpark-",
    "ar-bentonville-",
    "nd-fargo-",
    "il-cook-",
    "nj-dca-",
    "pa-philadelphia-",
    "wi-milwaukee-",
    "ny-nyc-",
    "wa-seattle-",
    "md-montgomery-",
    "fl-miamidade-",
    "mi-detroit-",
    "va-fairfax-",
    "oh-columbus-",
    "oh-cleveland-",
    "oh-cincinnati-",
    "pa-pittsburgh-pli-",
)

# Every record from these sources carries its own unique per-record ID
# (a real permit/case/award number from a structured source, not a
# derived slug) -- two records both matching this pattern are guaranteed
# different projects without needing an expensive fuzzy-name comparison,
# same logic as MUNI_ID_PREFIXES above but for infixes that recur across
# every state (federal sources) rather than one exact per-source prefix.
MUNI_ID_INFIXES = (
    "-sam-",
    "-usaspending-",
)

# (prefix, label, is_dedicated_local) -- order matters, first match wins.
# Add a new tuple here whenever a new state/source-specific pull script is
# built; DRI-alike statewide filings and hand-curated research default to
# "thin" via the fallback at the bottom of classify_source(). Shared here
# (rather than living only in scripts/compute-county-coverage.py, which it
# originated in) because scripts/load-corpus-to-postgres.py also needs it,
# to derive project_sources.source_name and project_events.event_type --
# and compute-county-coverage.py's hyphenated filename can't be imported as
# a module anyway.
#
# Was originally an allowlist of known-local prefixes (GA/NC only) -- went
# stale the moment the Agent-Per-State pipeline started adding real local
# sources for other states, since nothing forced a matching entry here.
# By 2026-07-31 that had silently misclassified ~90K real dedicated-local
# rows (TX Travis/Tarrant/Collin/etc., PA Pittsburgh, CA LA/SF, NY NYCDOB)
# as "thin". A project_id's second hyphen-segment is either a broad
# source-type token (small, stable vocabulary -- checked below) or a
# jurisdiction name (city/county -- the common case, and the one that
# keeps growing). Denylisting the broad tokens and defaulting everything
# else to local self-maintains as new county/city sources are added,
# instead of requiring a manual allowlist entry every time.
BROAD_SOURCE_TOKENS: dict[str, str] = {
    "sam": "Federal (SAM.gov)",
    "usaspending": "Federal (USAspending)",
    "dri": "Georgia DRI (statewide)",
    "dca": "NJ DCA (statewide)",
    "tdlr": "Texas TDLR TABS (statewide)",
    "statewide": "Statewide source",
    "act250": "Vermont Act 250 (statewide)",
}

# Optional prettier labels for specific known local prefixes (provider type,
# where known). Anything not listed here still classifies as local --
# just with a generic label derived from its jurisdiction segment.
LOCAL_SOURCE_LABELS: dict[str, str] = {
    "ga-fulton-": "Fulton County (ArcGIS)",
    "ga-alpharetta-": "Alpharetta (ArcGIS)",
    "ga-johnscreek-": "Johns Creek (ArcGIS)",
    "ga-marietta-": "Marietta (ArcGIS)",
    "ga-savannah-": "Savannah/SAGIS (ArcGIS)",
    "ga-atlanta-": "Atlanta (Accela)",
    "ga-gwinnett-": "Gwinnett (Accela)",
    "ga-cobb-": "Cobb (Accela)",
    "nc-mecklenburg-": "Mecklenburg County (ArcGIS)",
    "nc-wake-": "Wake County (ArcGIS)",
}


def classify_source(project_id: str) -> tuple[str, bool]:
    """Return (source_label, is_dedicated_local) for a project_id."""
    pid = (project_id or "").lower()
    for prefix, label in LOCAL_SOURCE_LABELS.items():
        if pid.startswith(prefix):
            return label, True

    parts = pid.split("-")
    if len(parts) < 2:
        return "Prior research", False

    token = parts[1]
    if token in BROAD_SOURCE_TOKENS:
        return BROAD_SOURCE_TOKENS[token], False

    return f"{token.replace('.', ' ').title()} (local source)", True


def derive_event_type(project_id: str, record_type: str | None) -> str:
    """Heuristic event_type for project_events, derived from project_id/
    record_type at load time rather than requiring every pull script to
    emit its own event stream (see docs/AGENT_STRATEGY.md-adjacent plan
    notes). DRI filings are a pre-permit announcement; SAM.gov postings are
    a solicitation (bid) stage; USAspending records an actual award;
    everything else defaults to permit-derived, since that's what most
    wired sources are (municipal/county ArcGIS/Accela pulls)."""
    pid = (project_id or "").lower()
    if "-dri-" in pid or record_type == "dri_filing":
        return "Announced"
    if "-sam-" in pid:
        return "Bid_Opened"
    if "-usaspending-" in pid:
        return "Awarded"
    return "Permit_Issued"


def slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "project"


def normalize_name(name: str) -> str:
    """Collapse punctuation and filler words for duplicate detection."""
    s = (name or "").lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(
        r"\b(the|a|an|project|phase|i|ii|iii|iv|revised|expansion|data center|campus)\b",
        " ",
        s,
    )
    return re.sub(r"\s+", " ", s).strip()


def is_record_specific_url(url: str) -> bool:
    u = (url or "").strip()
    if not u.startswith("http"):
        return False
    if GENERIC_SOURCE_URL.search(u):
        return False
    if re.search(r"(?i)(driid=|capid|permit[_-]?no=|recordid=|objectid=)", u):
        return True
    if re.search(r"(?i)/documents/|/files/|\.pdf($|\?)", u):
        return True
    # Press releases and one-off pages are specific enough to dedupe on.
    if len(u) > 60 and u.count("/") >= 5:
        return True
    return False


def source_urls(project: dict, *, record_specific_only: bool = True) -> set[str]:
    urls: set[str] = set()
    for src in project.get("sources") or []:
        if isinstance(src, dict):
            u = (src.get("url") or "").strip()
            if not u.startswith("http"):
                continue
            if record_specific_only and not is_record_specific_url(u):
                continue
            urls.add(u)
    return urls


def completeness(project: dict) -> int:
    score = 0
    for key in (
        "name",
        "description",
        "owner",
        "architect",
        "general_contractor",
        "opened_or_announced_date",
    ):
        if project.get(key):
            score += 2
    if project.get("estimated_value_usd"):
        score += 3
    if project.get("square_footage"):
        score += 2
    score += len(project.get("sources") or [])
    score += len(project.get("key_specs") or [])
    if "dri-" in (project.get("id") or ""):
        score += 5
    return score


def prefer_canonical(a: dict, b: dict) -> tuple[dict, dict]:
    """Return (primary, secondary) for merge."""
    if "dri-" in (a.get("id") or "") and "dri-" not in (b.get("id") or ""):
        return a, b
    if "dri-" in (b.get("id") or "") and "dri-" not in (a.get("id") or ""):
        return b, a
    if completeness(a) >= completeness(b):
        return a, b
    return b, a


def merge_projects(primary: dict, secondary: dict) -> dict:
    """Merge secondary into primary; primary id is kept."""
    out = dict(primary)

    if len(secondary.get("name") or "") > len(out.get("name") or ""):
        out["name"] = secondary["name"]

    for key in ("description", "open_for", "owner", "architect", "general_contractor"):
        if not out.get(key) and secondary.get(key):
            out[key] = secondary[key]
        elif secondary.get(key) and secondary[key] not in (out.get(key) or ""):
            out[key] = f"{out.get(key, '').rstrip('.')}. {secondary[key]}".strip()

    for key in (
        "estimated_value_usd",
        "square_footage",
        "opened_or_announced_date",
        "latitude",
        "longitude",
        "zip",
    ):
        if out.get(key) in (None, "", 0) and secondary.get(key):
            out[key] = secondary[key]

    def uniq_list(items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        out_list: list[Any] = []
        for item in items:
            key = str(item).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out_list.append(item)
        return out_list

    for key in ("key_specs", "mentioned_brands", "competitor_watch"):
        out[key] = uniq_list([*(out.get(key) or []), *(secondary.get(key) or [])])

    seen_urls: set[str] = set()
    merged_sources: list[dict] = []
    for src in [*(out.get("sources") or []), *(secondary.get("sources") or [])]:
        if not isinstance(src, dict):
            continue
        url = (src.get("url") or "").strip()
        title = (src.get("title") or "").strip()
        dedupe_key = url or title.lower()
        if dedupe_key in seen_urls:
            continue
        seen_urls.add(dedupe_key)
        merged_sources.append({"title": title or url, "url": url})
    out["sources"] = merged_sources

    return out


def _muni_permit_id(pid: str) -> bool:
    pid = (pid or "").lower()
    if any(pid.startswith(prefix) for prefix in MUNI_ID_PREFIXES):
        return True
    return any(infix in pid for infix in MUNI_ID_INFIXES)


def _dri_id(pid: str) -> bool:
    return "ga-dri-" in (pid or "").lower() or re.search(r"-dri-\d", (pid or "").lower())


def names_compatible(a: dict, b: dict) -> bool:
    na, nb = normalize_name(a.get("name", "")), normalize_name(b.get("name", ""))
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 12 and shorter in longer:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= 0.92


def same_project(a: dict, b: dict) -> bool:
    if (a.get("state") or "").upper() != (b.get("state") or "").upper():
        return False
    if (a.get("county") or "").lower() != (b.get("county") or "").lower():
        return False

    aid = (a.get("id") or "").lower()
    bid = (b.get("id") or "").lower()
    if aid == bid:
        return True

    # Different permit case numbers or DRI filings are different projects.
    if aid != bid:
        if _muni_permit_id(aid) and _muni_permit_id(bid):
            return False
        if _dri_id(aid) and _dri_id(bid):
            return False

    shared = source_urls(a) & source_urls(b)
    if shared and names_compatible(a, b):
        return True

    na, nb = normalize_name(a.get("name", "")), normalize_name(b.get("name", ""))
    if not na or not nb:
        return False
    if na == nb:
        return True

    # Cross-source headline variants (DRI title vs press release), research only.
    if _muni_permit_id(aid) or _muni_permit_id(bid):
        return False

    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(shorter) >= 12 and shorter in longer:
        return True

    return False


def ensure_state_prefixed(project: dict, state_code: str) -> dict:
    state = (project.get("state") or state_code).upper()
    pid = (project.get("id") or slugify(project.get("name", "unknown"))).strip()
    if not pid.startswith(f"{state.lower()}-"):
        pid = f"{state.lower()}-{pid}"
    project["id"] = pid[:ID_MAX]
    project["state"] = state
    return project


def assign_unique_ids(projects: list[dict], state_code: str) -> list[dict]:
    """Ensure every project has a unique, state-prefixed id."""
    out: list[dict] = []
    seen: set[str] = set()
    for p in projects:
        p = ensure_state_prefixed(dict(p), state_code)
        base = p["id"]
        candidate = base
        n = 2
        while candidate in seen:
            suffix = f"-{n}"
            candidate = f"{base[: ID_MAX - len(suffix)]}{suffix}"
            n += 1
        p["id"] = candidate
        seen.add(candidate)
        out.append(p)
    return out


def _stable_canonical_id(a_id: str, b_id: str) -> str:
    """Pick which of two merging records' ids survives -- independent of
    field completeness, which can change between corpus rebuilds as
    sources get enriched. prefer_canonical() picks which record's *fields*
    seed the merge based on completeness, which is fine and should stay
    that way; but if the *id* also followed completeness, a project's
    "permanent" id could silently change identity the next time a source
    happens to have slightly more data -- exactly what an MLS-style
    permanent ID can't tolerate (load-corpus-to-postgres.py upserts on
    project_id, so a changed id looks like a brand-new project: a fresh
    project_sk gets minted and the old row is orphaned). DRI ids are kept
    as the canonical source when present (matches prefer_canonical()'s
    existing DRI preference); otherwise the lexicographically smaller id
    wins -- arbitrary, but deterministic and order-independent, so the
    same pair of ids always resolves to the same survivor no matter which
    run's data happened to be more complete."""
    if "dri-" in a_id and "dri-" not in b_id:
        return a_id
    if "dri-" in b_id and "dri-" not in a_id:
        return b_id
    return a_id if a_id <= b_id else b_id


SHINGLE_LEN = 12          # matches same_project()'s minimum substring length
MAX_POSTINGS = 400        # a key shared by more rows than this is not discriminative


def _blocking_keys(p: dict) -> set[str]:
    """Keys such that ANY pair same_project() could accept shares at least one.

    This is the correctness argument for the prefilter, and it has to be
    checked against every branch of same_project(), not just the obvious one:

      1. aid == bid                      -> both emit  id:<id>
      2. shared source_urls + names ok   -> both emit  u:<url> for that url
      3. normalize_name equal            -> both emit  n:<name>
      4. shorter (>=12) inside longer    -> every SHINGLE_LEN-gram of the
                                            shorter name is also a gram of the
                                            longer, so both emit that s:<gram>

    Branch 4 is why a plain name hash is NOT a safe prefilter -- "Midtown
    Tower Phase II" and "Atlanta Midtown Tower Phase II Expansion" hash
    differently and would never be compared, silently losing a merge the
    current code finds. Character shingles are the cheapest key that keeps
    substring containment blockable.
    """
    keys: set[str] = set()
    pid = (p.get("id") or "").lower()
    if pid:
        keys.add(f"id:{pid}")
    for u in source_urls(p):
        keys.add(f"u:{u}")
    n = normalize_name(p.get("name", ""))
    if n:
        keys.add(f"n:{n}")
        if len(n) >= SHINGLE_LEN:
            for i in range(len(n) - SHINGLE_LEN + 1):
                keys.add(f"s:{n[i:i + SHINGLE_LEN]}")
    return keys


def _candidate_pairs(bucket: list[dict]) -> set[tuple[int, int]]:
    """Index -> only the pairs sharing a blocking key. This is what turns
    O(k^2) into roughly O(k * avg_postings)."""
    from collections import defaultdict as _dd

    index: dict[str, list[int]] = _dd(list)
    for i, rec in enumerate(bucket):
        for k in _blocking_keys(rec):
            index[k].append(i)

    pairs: set[tuple[int, int]] = set()
    for key, idxs in index.items():
        if len(idxs) < 2:
            continue
        # A key held by hundreds of records is a FEED-level artifact (a
        # dataset landing url, a boilerplate name fragment), not evidence of
        # identity. Expanding it would re-create the very O(k^2) blowup this
        # prefilter exists to remove -- one 30k-row bucket is 450M
        # comparisons and hours of 100% CPU with no output. Skipping it is a
        # deliberate, logged trade-off: exact-id and full-name keys are
        # unaffected, so no exact duplicate is ever missed by this.
        if len(idxs) > MAX_POSTINGS:
            continue
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                pairs.add((idxs[a], idxs[b]))
    return pairs


def _dedupe_bucket(bucket: list[dict]) -> int:
    """Blocking-prefiltered dedupe within one (state, county) bucket.

    Was a single O(k^2) pass. Once a bucket reached tens of thousands of rows
    (NJ after the 2025-01-01 backfill) the comparison count exploded and
    merge-national-corpus.py ran at 100% CPU for HOURS with zero progress
    output, because it only printed at the end. That is the bug this replaces.

    Candidate pairs now come from shared blocking keys, then same_project()
    adjudicates each candidate exactly as before -- the decision logic is
    untouched, only the set of pairs it is asked about shrinks.

    Repeats until a pass makes no merges, because merging rewrites a record's
    name and source urls and can therefore create a match that did not exist
    when the index was built. Merges are rare, so this is typically two passes.
    """
    total = 0
    for _ in range(10):  # bounded: never spin forever on pathological data
        pairs = _candidate_pairs(bucket)
        if not pairs:
            break
        dead: set[int] = set()
        merges = 0
        for i, j in sorted(pairs):
            if i in dead or j in dead:
                continue
            if not same_project(bucket[i], bucket[j]):
                continue
            a_id, b_id = bucket[i].get("id", ""), bucket[j].get("id", "")
            primary, secondary = prefer_canonical(bucket[i], bucket[j])
            merged = merge_projects(primary, secondary)
            merged["id"] = _stable_canonical_id(a_id, b_id)
            bucket[i] = merged
            dead.add(j)
            merges += 1
        if dead:
            bucket[:] = [r for k, r in enumerate(bucket) if k not in dead]
        total += merges
        if merges == 0:
            break
    return total


def dedupe_projects(projects: list[dict], state_code: str) -> tuple[list[dict], int]:
    """Merge duplicate records; return (projects, merges_performed).

    Buckets records by (state, county) before comparing, since same_project()
    always rejects a pair whose state or county differ before doing anything
    else -- comparing across buckets can never find a match. This turns the
    scan from O(n^2) over the whole batch into O(sum(k_i^2)) over each
    bucket's size, with no change in which duplicates are found (an earlier
    single-pass-no-bucketing version already fixed a worse O(n^2 * merges)
    bug where the scan restarted from index 0 on every merge; bucketing is
    the next win once record counts grow past a single small county, e.g.
    a 24-month North Carolina pull spanning several counties at once).
    """
    normalized = [ensure_state_prefixed(dict(p), state_code) for p in projects]

    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in normalized:
        key = ((p.get("state") or "").upper(), (p.get("county") or "").lower())
        buckets[key].append(p)

    merges = 0
    deduped: list[dict] = []
    for bucket in buckets.values():
        merges += _dedupe_bucket(bucket)
        deduped.extend(bucket)

    return assign_unique_ids(deduped, state_code), merges


# Vermont has no county-level government function relevant to permitting --
# Act 250 (scripts/pull-county-arcgis.py's pull_act250) reports a project's
# *town*, not a county, and using the town name as the `county` field
# directly inflated county_coverage's distinct-county count for VT from 14
# (real) to 214 (one per distinct town) before this was caught. Source:
# Wikipedia's "List of towns in Vermont" (all 14 counties, 251
# municipalities), 2026-07-27.
VT_TOWN_TO_COUNTY: dict[str, str] = {
    "Burlington": "Chittenden", "South Burlington": "Chittenden", "Colchester": "Chittenden", "Rutland": "Rutland",
    "Bennington": "Bennington", "Brattleboro": "Windham", "Essex": "Chittenden", "Milton": "Chittenden", "Hartford": "Windsor",
    "Essex Junction": "Chittenden", "Williston": "Chittenden", "Middlebury": "Addison", "Springfield": "Windsor", "Barre": "Washington",
    "Montpelier": "Washington", "Winooski": "Chittenden", "Shelburne": "Chittenden", "St. Johnsbury": "Caledonia", "St. Albans": "Franklin",
    "Swanton": "Franklin", "Northfield": "Washington", "Lyndon": "Caledonia", "Morristown": "Lamoille", "Waterbury": "Washington",
    "Stowe": "Lamoille", "Jericho": "Chittenden", "Fairfax": "Franklin", "Georgia": "Franklin", "Rockingham": "Windham",
    "Randolph": "Orange", "Hinesburg": "Chittenden", "Derby": "Orleans", "Manchester": "Bennington", "Castleton": "Rutland",
    "Newport": "Orleans", "Richmond": "Chittenden", "Brandon": "Rutland", "Cambridge": "Lamoille", "Charlotte": "Chittenden",
    "Bristol": "Addison", "Norwich": "Windsor", "Shaftsbury": "Bennington", "Windsor": "Windsor", "Williamstown": "Orange",
    "Johnson": "Lamoille", "Highgate": "Franklin", "Hartland": "Windsor", "Pownal": "Bennington", "Underhill": "Chittenden",
    "Hyde Park": "Lamoille", "Poultney": "Rutland", "Westminster": "Windham", "Chester": "Windsor", "Woodstock": "Windsor",
    "Hardwick": "Caledonia", "Barton": "Orleans", "Pittsford": "Rutland", "Berlin": "Washington", "Weathersfield": "Windsor",
    "Enosburgh": "Franklin", "Bradford": "Orange", "Thetford": "Orange", "Royalton": "Windsor", "Fair Haven": "Rutland",
    "Ferrisburgh": "Addison", "Putney": "Windham", "East Montpelier": "Washington", "Vergennes": "Addison", "Arlington": "Bennington",
    "Clarendon": "Rutland", "Richford": "Franklin", "Danville": "Caledonia", "Newbury": "Orange", "Wilmington": "Windham",
    "West Rutland": "Rutland", "Vernon": "Windham", "Ludlow": "Windsor", "Sheldon": "Franklin", "Dorset": "Bennington",
    "Wallingford": "Rutland", "Guilford": "Windham", "Alburgh": "Grand Isle", "Grand Isle": "Grand Isle", "Monkton": "Addison",
    "Westford": "Chittenden", "Fairfield": "Franklin", "Warren": "Washington", "Bethel": "Windsor", "Huntington": "Chittenden",
    "Londonderry": "Windham", "Dummerston": "Windham", "Waitsfield": "Washington", "Dover": "Windham", "Middlesex": "Washington",
    "Proctor": "Rutland", "Starksboro": "Addison", "Moretown": "Washington", "Marlboro": "Windham", "Troy": "Orleans",
    "New Haven": "Addison", "South Hero": "Grand Isle", "Wolcott": "Lamoille", "Barnet": "Caledonia", "Calais": "Washington",
    "Burke": "Caledonia", "Newfane": "Windham", "Marshfield": "Washington", "Sharon": "Windsor", "Berkshire": "Franklin",
    "Corinth": "Orange", "Cabot": "Washington", "Pawlet": "Rutland", "Duxbury": "Washington", "Killington": "Rutland",
    "Cavendish": "Windsor", "Mount Holly": "Rutland", "Addison": "Addison", "Fayston": "Washington", "Franklin": "Franklin",
    "Fletcher": "Franklin", "West Windsor": "Windsor", "Whitingham": "Windham", "Craftsbury": "Orleans", "Eden": "Lamoille",
    "Tunbridge": "Orange", "Lincoln": "Addison", "Bolton": "Chittenden", "Townshend": "Windham", "Danby": "Rutland",
    "Bakersfield": "Franklin", "Waterford": "Caledonia", "Shoreham": "Addison", "Lunenburg": "Essex", "Brookfield": "Orange",
    "Orwell": "Addison", "Chittenden": "Rutland", "Plainfield": "Washington", "Chelsea": "Orange", "Irasburg": "Orleans",
    "Bridport": "Addison", "Salisbury": "Addison", "Wells": "Rutland", "Braintree": "Orange", "Cornwall": "Addison",
    "Topsham": "Orange", "Montgomery": "Franklin", "Winhall": "Bennington", "Ryegate": "Caledonia", "Brighton": "Essex",
    "Mendon": "Rutland", "Concord": "Essex", "Glover": "Orleans", "Coventry": "Orleans", "Rochester": "Windsor",
    "Shrewsbury": "Rutland", "Strafford": "Orange", "Sunderland": "Bennington", "Orange": "Orange", "Brownington": "Orleans",
    "Washington": "Orange", "Charleston": "Orleans", "Jamaica": "Windham", "Barnard": "Windsor", "Leicester": "Addison",
    "Fairlee": "Orange", "Groton": "Caledonia", "Albany": "Orleans", "Benson": "Rutland", "Worcester": "Washington",
    "Walden": "Caledonia", "North Hero": "Grand Isle", "Woodbury": "Washington", "Pomfret": "Windsor", "Sutton": "Caledonia",
    "Bridgewater": "Windsor", "Canaan": "Essex", "Lowell": "Orleans", "Elmore": "Lamoille", "Wardsboro": "Windham",
    "Stamford": "Bennington", "Weybridge": "Addison", "Greensboro": "Orleans", "Middletown Springs": "Rutland", "St. George": "Chittenden",
    "Halifax": "Windham", "Wheelock": "Caledonia", "Ripton": "Addison", "Hubbardton": "Rutland", "Stockbridge": "Windsor",
    "Peacham": "Caledonia", "Readsboro": "Bennington", "Rupert": "Bennington", "Reading": "Windsor", "Waterville": "Lamoille",
    "Sheffield": "Caledonia", "Roxbury": "Washington", "Vershire": "Orange", "Panton": "Addison", "Grafton": "Windham",
    "Plymouth": "Windsor", "Morgan": "Orleans", "Holland": "Orleans", "Weston": "Windsor", "West Fairlee": "Orange",
    "Newark": "Caledonia", "Kirby": "Caledonia", "Andover": "Windsor", "Tinmouth": "Rutland", "Jay": "Orleans",
    "Sudbury": "Rutland", "Brookline": "Windham", "Westfield": "Orleans", "Peru": "Bennington", "Pittsfield": "Rutland",
    "Isle La Motte": "Grand Isle", "Windham": "Windham", "Waltham": "Addison", "Stratton": "Windham", "Whiting": "Addison",
    "Sandgate": "Bennington", "Athens": "Windham", "Ira": "Rutland", "Hancock": "Addison", "Belvidere": "Lamoille",
    "Westmore": "Orleans", "Woodford": "Bennington", "Granville": "Addison", "East Haven": "Essex", "Guildhall": "Essex",
    "West Haven": "Rutland", "Baltimore": "Windsor", "Bloomfield": "Essex", "Maidstone": "Essex", "Mount Tabor": "Rutland",
    "Stannard": "Caledonia", "Landgrove": "Bennington", "Goshen": "Addison", "Norton": "Essex", "Searsburg": "Bennington",
    "Brunswick": "Essex", "Lemington": "Essex", "Granby": "Essex", "Victory": "Essex",
}


def vt_county_for_town(town: str) -> str:
    """Real Vermont county for a town name, falling back to the town name
    itself if genuinely unmapped (shouldn't happen -- all 214 towns seen
    in live Act 250 data resolved cleanly as of 2026-07-27)."""
    t = (town or "").strip()
    t = re.sub(r",?\s*Town of$", "", t)
    t = re.sub(r"\s+(City|Town)$", "", t)
    t = t.replace("Saint ", "St. ")
    return VT_TOWN_TO_COUNTY.get(t, town)
