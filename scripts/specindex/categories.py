"""Canonicalise product-category tags.

MEASURED 2026-08-05 over 591,618 projects, 292 distinct tags in
projects.competitor_watch. The dropdown built from them is unusable, for two
reasons that pull in opposite directions:

  THE HEAD FILTERS NOTHING.
      lighting          578,190   97.7% of all projects
      hvac              578,114   97.7%
      fire suppression  562,826   95.1%
      roofing           521,665   88.2%
      flooring          469,694   79.4%
  Selecting "lighting" returns essentially the entire corpus. These are
  TEMPLATE DEFAULTS stamped on every commercial permit, not detected facts --
  the same finding already recorded for competitor_watch generally. A filter
  that matches 97.7% of rows is not a filter.

  THE TAIL IS NOISE.
  279 of the 292 tags appear on fewer than 1,000 projects EACH, and together
  account for 1,377 tag instances. So 279 of the options exist for roughly
  0.2% of the data, while presenting themselves as equals to the head.

  Plus 22 near-duplicate families and 4 case-duplicates:
      'hvac' (578,114) and 'HVAC' (110)      -- the same trade, split
      'flooring' and ' flooring'              -- leading whitespace
      'doors and hardware' / 'doors/hardware'
      'medical gas' / 'medical gas systems'
      'cooling' / 'cooling systems'
      'lab equipment' / 'lab systems'

This module normalises the tags. It does NOT invent a taxonomy -- merging is
limited to case, whitespace, punctuation and a small explicit synonym table,
because collapsing genuinely distinct trades to shrink a list would destroy
signal to fix cosmetics.

The honest fix for the head is upstream: competitor_watch needs to reflect
real per-project detection instead of a stamped template. Until it does, the
UI should say which tags are broad defaults rather than implying they
discriminate.
"""
from __future__ import annotations

import re

# Tags on >50% of the corpus. Kept and shown, but grouped separately so the
# UI can be honest that selecting one narrows almost nothing.
BROAD_DEFAULT_TAGS = {"lighting", "hvac", "fire suppression", "roofing", "flooring"}

# Explicit synonyms only. Each pair is the SAME trade written two ways --
# never two different trades merged for tidiness.
SYNONYMS = {
    "doors/hardware": "doors and hardware",
    "medical gas systems": "medical gas",
    "cooling systems": "cooling",
    "lab systems": "lab equipment",
    "backup power/generators": "backup power",
    "backup generators": "backup power",
    "access control & security": "access control",
    "accessibility systems": "accessibility",
    "av systems": "av",
    "av/conference systems": "av",
    "avl technology": "av",
    "coating systems": "coatings",
    "concrete/paving": "concrete paving",
    "clean room": "cleanroom",
    "clean room systems": "cleanroom",
    "cleanroom systems": "cleanroom",
    "cleanroom finishes": "cleanroom",
}


def canonical(tag: str) -> str:
    """Case-fold, strip, collapse whitespace, then apply synonyms.

    Returns "" for anything empty so callers can drop it -- a blank tag in a
    filter list is a row users can select to get nothing.
    """
    if not tag:
        return ""
    t = re.sub(r"\s+", " ", tag.strip().lower())
    t = t.strip(" -/,")
    return SYNONYMS.get(t, t)


def is_broad_default(tag: str) -> bool:
    return canonical(tag) in BROAD_DEFAULT_TAGS


def group_for_ui(tags_with_counts: list[tuple[str, int]], total_projects: int,
                 tail_threshold: int = 1000) -> dict:
    """Split canonical tags into the three groups a usable dropdown needs.

    broad     -- matches most of the corpus; near-useless as a filter, but
                 users look for them by name, so keep them and LABEL them.
    specific  -- the genuinely discriminating middle. This is the useful set.
    rare      -- below tail_threshold; collapsed so 279 near-empty options do
                 not sit alongside the eight that work.
    """
    merged: dict[str, int] = {}
    for tag, n in tags_with_counts:
        c = canonical(tag)
        if c:
            merged[c] = merged.get(c, 0) + n
    broad, specific, rare = [], [], []
    for c, n in sorted(merged.items(), key=lambda kv: -kv[1]):
        if c in BROAD_DEFAULT_TAGS or (total_projects and n / total_projects > 0.5):
            broad.append((c, n))
        elif n >= tail_threshold:
            specific.append((c, n))
        else:
            rare.append((c, n))
    return {"broad": broad, "specific": specific, "rare": rare,
            "merged_from": len(tags_with_counts), "merged_to": len(merged)}
