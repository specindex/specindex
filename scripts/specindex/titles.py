"""Project-title composition.

THE DEFECT (03_project_record.md, change 04). The live record read
"B28 High Containment Lab Eo 14398" -- an executive-order number fused into a
building name and sentence-cased into "Eo". The title is composed from
whatever string the source supplied, which for federal records is often a
solicitation line rather than a project name.

Measured across 591,617 titles: 488 (0.08%) carry an order, solicitation, RFP,
contract or project number. Small as a share, and highly visible: they are
concentrated in exactly the federal records that look most impressive in a
demo.

TWO RULES THAT MATTER

1. The identifier is EXTRACTED, not deleted. EO 14398 is a genuinely useful
   fact about that contract -- it belongs on a compliance line, not in the
   bin. Deleting it would trade one defect for a data loss.

2. NEVER return an empty title. Some records are ONLY an identifier
   ("34ST38900723", "Solicitation: W911SA26RA006"). Stripping leaves nothing,
   and a blank title is worse than an ugly one -- it breaks the row, the tab
   title and every link. When cleaning would empty the string, the original is
   kept and reported instead.
"""
from __future__ import annotations

import re

# Ordered: the most specific pattern first, so "Solicitation No. X" is not
# partly consumed by a looser rule.
_PATTERNS: list[tuple[str, str]] = [
    ("executive_order", r"\bE\.?\s?O\.?\s*#?\s*\d{4,5}\b"),
    ("solicitation", r"\bsolicitation\s*(?:no\.?|number|#)?\s*:?\s*[A-Z0-9][A-Z0-9-]{5,}\b"),
    ("rfp", r"\b(?:RFP|RFQ|IFB|BAA)\s*(?:no\.?|#)?\s*:?\s*[A-Z0-9][A-Z0-9-]{3,}\b"),
    ("contract", r"\b(?:contract|award)\s*(?:no\.?|#)\s*:?\s*[A-Z0-9][A-Z0-9-]{4,}\b"),
    ("project_no", r"\bproject\s*(?:no\.?|#)\s*:?\s*[A-Z0-9][A-Z0-9-]{3,}\b"),
    # A bare federal identifier used AS the whole title, e.g. "34ST38900723".
    # Detected so the assertion sees it; clean_title keeps the original,
    # because stripping it leaves nothing at all.
    ("gov_id", r"\b\d{2}[A-Z]{2,4}\d{5,}\b"),
]

# Punctuation and connectives left stranded once an identifier is removed --
# "Lab Eo 14398" -> "Lab" needs no cleanup, but "Eo 14398, Construct A Pavilion"
# -> ", Construct A Pavilion" does. Same class of bug as the ", Georgia"
# location defect: removing a part must remove its punctuation too.
_STRANDED = re.compile(r"^[\s,;:.\-–—/]+|[\s,;:.\-–—/]+$")
_DOUBLE_SEP = re.compile(r"\s*[,;]\s*(?=[,;])|\s{2,}")
# Brackets emptied by the removal. "Building 9122 (Project #44153)" became
# "Building 9122 ( )" -- the same stranded-punctuation bug as the ", Georgia"
# location defect, one nesting level in. Removing a part must remove whatever
# was wrapping it.
_EMPTY_WRAP = re.compile(r"[\(\[\{]\s*[\)\]\}]")


# An identifier ALWAYS contains a digit. Without this, "PROJECT NO CHANGE"
# matched as a project number and "SIDEWALK REPLACEMENT AND VAULT REPAIR
# PROJECT NO CHANGE" was truncated to "SIDEWALK REPLACEMENT AND VAULT REPAIR".
# Caught in the dry run: a cleaner that mangles a real title is worse than the
# defect it fixes, because the original is gone.
_HAS_DIGIT = re.compile(r"\d")


def clean_title(raw: str | None) -> tuple[str, dict[str, str]]:
    """Return (cleaned_title, {kind: identifier}).

    If cleaning would leave nothing usable, the ORIGINAL is returned unchanged
    and the identifiers are still reported, so a caller can surface them
    without mangling the record.
    """
    if not raw or not raw.strip():
        return (raw or ""), {}
    title = raw
    found: dict[str, str] = {}
    for kind, pat in _PATTERNS:
        m = re.search(pat, title, re.I)
        if m and _HAS_DIGIT.search(m.group(0)):
            found[kind] = re.sub(r"\s+", " ", m.group(0)).strip(" :#")
            title = title[: m.start()] + " " + title[m.end():]
    if not found:
        return raw, {}
    title = _EMPTY_WRAP.sub("", title)
    title = _DOUBLE_SEP.sub(" ", title)
    title = _STRANDED.sub("", title).strip()
    title = re.sub(r"\s{2,}", " ", title)
    # A title that is only an identifier, or reduced to a fragment, is worse
    # cleaned than left alone.
    if len(title) < 6:
        return raw, found
    return title, found


def title_has_identifier(raw: str | None) -> str | None:
    """The assertion helper: returns the offending fragment, or None."""
    if not raw:
        return None
    for _, pat in _PATTERNS:
        m = re.search(pat, raw, re.I)
        if m and _HAS_DIGIT.search(m.group(0)):
            return m.group(0)
    return None
