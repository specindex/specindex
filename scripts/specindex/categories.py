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


# ---------------------------------------------------------------------------
# GOVERNED VOCABULARY (design review, 2026-08-05)
#
# "Map every category to a CSI division and hold the customer-facing list to
# roughly 30 governed values, with the raw string kept on the record for
# provenance. A rep who sees two spellings of the same thing stops trusting
# the count next to it."
#
# That last sentence is the whole argument. The cost of a messy vocabulary is
# not ugliness, it is that the NUMBER beside each option stops being believed
# -- and the number is what we sell.
#
# Two rules make this safe:
#   1. The raw string is never destroyed. governed() maps for DISPLAY; the
#      original stays on the record, so a mapping mistake is reversible and
#      provenance survives.
#   2. Anything unmapped falls through to UNGOVERNED rather than being forced
#      into the nearest bucket. A wrong division is worse than an honest
#      "other" -- it would put a manufacturer in a trade they do not sell into.
# ---------------------------------------------------------------------------

UNGOVERNED = ("99", "Other / ungoverned")

# division code -> customer-facing label. MasterFormat divisions, which is the
# same axis the spec-extraction wedge uses, so the filter and the product
# finally speak one language.
CSI_DIVISIONS: dict[str, str] = {
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood & Plastics",
    "07": "Thermal & Moisture (Roofing)",
    "08": "Openings (Doors, Glazing)",
    "09": "Finishes",
    "10": "Specialties",
    "11": "Equipment",
    "12": "Furnishings (FF&E)",
    "13": "Special Construction",
    "14": "Conveying (Elevators)",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "HVAC",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety & Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "34": "Transportation",
    "40": "Process Interconnections",
    "41": "Material Processing",
    "48": "Electrical Power Generation",
    UNGOVERNED[0]: UNGOVERNED[1],
}

# Substring -> division. Ordered longest-first at match time so "fire
# suppression" is not captured by "fire".
_TAG_TO_DIVISION: list[tuple[str, str]] = [
    ("fire suppression", "21"), ("fire protection", "21"), ("sprinkler", "21"),
    ("plumbing", "22"), ("medical gas", "22"), ("bathroom fixtures", "22"),
    ("hvac", "23"), ("chiller", "23"), ("cooling", "23"), ("boiler", "23"),
    ("air handling", "23"), ("climate control", "23"), ("ventilation", "23"),
    ("refrigeration", "23"), ("compressed air", "23"),
    ("building automation", "25"), ("bms", "25"), ("controls", "25"),
    ("electrical", "26"), ("lighting", "26"), ("switchgear", "26"),
    ("generator", "26"), ("backup power", "26"), ("ups", "26"),
    ("battery storage", "26"), ("power distribution", "26"), ("solar", "26"),
    ("communication", "27"), ("av", "27"), ("data center", "27"),
    ("structured cabling", "27"), ("network", "27"),
    ("security", "28"), ("access control", "28"), ("surveillance", "28"),
    ("fire alarm", "28"),
    ("elevator", "14"), ("escalator", "14"), ("conveyor", "14"), ("lift", "14"),
    ("roofing", "07"), ("waterproofing", "07"), ("insulation", "07"),
    ("glazing", "08"), ("curtain wall", "08"), ("doors", "08"),
    ("windows", "08"), ("storefront", "08"), ("hardware", "08"),
    ("flooring", "09"), ("acoustic", "09"), ("ceiling", "09"),
    ("paint", "09"), ("coating", "09"), ("finishes", "09"), ("tile", "09"),
    ("concrete", "03"), ("paving", "32"), ("masonry", "04"),
    ("structural steel", "05"), ("metals", "05"),
    ("casework", "06"), ("cabinetry", "06"), ("millwork", "06"),
    ("ff&e", "12"), ("furniture", "12"), ("seating", "12"),
    ("cleanroom", "13"), ("clean room", "13"), ("pool", "13"),
    ("dock equipment", "11"), ("kitchen equipment", "11"), ("lab equipment", "11"),
    ("laundry", "11"), ("appliance", "11"), ("bottling", "41"),
    ("signage", "10"), ("lockers", "10"), ("partitions", "10"),
    ("landscape", "32"), ("irrigation", "32"), ("fencing", "32"),
    ("utilities", "33"), ("civil", "33"), ("stormwater", "33"),
    ("accessibility", "10"), ("elevator", "14"),
]


def division_for(tag: str) -> tuple[str, str]:
    """(division_code, label) for a raw tag. UNGOVERNED when nothing matches.

    Longest substring first, so 'fire suppression' beats a bare 'fire' and
    'access control' is not swallowed by 'control'.
    """
    c = canonical(tag)
    if not c:
        return UNGOVERNED
    for needle, div in sorted(_TAG_TO_DIVISION, key=lambda kv: -len(kv[0])):
        if needle in c:
            return div, CSI_DIVISIONS[div]
    return UNGOVERNED


def governed_facets(tags_with_counts: list[tuple[str, int]]) -> list[dict]:
    """Collapse raw tags into governed divisions with counts, for the filter UI.

    The raw tag is retained in `raw_tags` so a record can still show what the
    source actually said, and so a mapping error is traceable rather than
    baked in.
    """
    agg: dict[str, dict] = {}
    for tag, n in tags_with_counts:
        code, label = division_for(tag)
        e = agg.setdefault(code, {"division": code, "label": label,
                                  "count": 0, "raw_tags": []})
        e["count"] += n
        e["raw_tags"].append(tag)
    return sorted(agg.values(), key=lambda e: (e["division"] == UNGOVERNED[0], -e["count"]))


# ---------------------------------------------------------------------------
# Project types. 87 distinct values today, 13 of which are full DESCRIPTIONS
# that leaked into a type field -- e.g. "Industrial / Data Center (300,000 sq
# ft, 99 MW capacity)". Each appears exactly once and each becomes its own
# dropdown option, which is how a filter list acquires entries that match a
# single row.
# ---------------------------------------------------------------------------

PROJECT_TYPES = (
    "commercial", "office", "retail", "industrial", "warehouse", "education",
    "healthcare", "hospitality", "civic", "institutional", "residential",
    "mixed_use", "data_center", "infrastructure", "religious", "recreation",
    "transportation", "utility", "other",
)

_TYPE_ALIASES = {
    "mixed use": "mixed_use", "mixed-use": "mixed_use",
    "data centre": "data_center", "datacenter": "data_center",
    "school": "education", "university": "education", "k-12": "education",
    "hospital": "healthcare", "medical": "healthcare", "clinic": "healthcare",
    "hotel": "hospitality", "restaurant": "hospitality",
    "government": "civic", "municipal": "civic",
    "distribution": "warehouse", "logistics": "warehouse",
    "multifamily": "residential", "apartment": "residential",
}


def governed_project_type(raw: str | None) -> str:
    """Map a raw type to the fixed list. Long free text degrades to 'other'.

    A 60-character description is not a type, and letting one through creates
    a filter option that matches exactly one project.
    """
    if not raw:
        return "other"
    t = re.sub(r"\s+", " ", raw.strip().lower())
    if t in PROJECT_TYPES:
        return t
    for alias, canon in _TYPE_ALIASES.items():
        if alias in t:
            return canon
    for pt in PROJECT_TYPES:
        if pt.replace("_", " ") in t:
            return pt
    return "other"
