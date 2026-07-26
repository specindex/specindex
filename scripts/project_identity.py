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
)


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

    for key in ("estimated_value_usd", "square_footage", "opened_or_announced_date"):
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
    return any(pid.startswith(prefix) for prefix in MUNI_ID_PREFIXES)


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


def _dedupe_bucket(bucket: list[dict]) -> int:
    """In-place pairwise dedupe within one (state, county) bucket. Returns
    merges performed. Single pass, O(k^2) over the bucket -- see
    dedupe_projects() for why restarting from index 0 on every merge was
    the previous performance bug."""
    merges = 0
    i = 0
    while i < len(bucket):
        j = i + 1
        while j < len(bucket):
            if same_project(bucket[i], bucket[j]):
                a_id, b_id = bucket[i].get("id", ""), bucket[j].get("id", "")
                primary, secondary = prefer_canonical(bucket[i], bucket[j])
                merged = merge_projects(primary, secondary)
                merged["id"] = _stable_canonical_id(a_id, b_id)
                bucket[i] = merged
                del bucket[j]
                merges += 1
                continue  # re-check the (possibly enriched) record i against the next j
            j += 1
        i += 1
    return merges


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
