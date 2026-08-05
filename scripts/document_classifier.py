"""Shared document classification: file class + priority rank.

ONE implementation, imported by capture (step 8), extraction routing (step 9)
and position computation (step 10). Three copies would drift, and a
classifier that disagrees with itself across steps produces documents that are
downloaded as rank 1 and then extracted as rank 4.

THE RANKING, from docs/AGENT_STRATEGY.md:

    1 addenda      -- amendments and pre-bid Q&A. THE MOAT. Substitution
                      rulings live here and nowhere else, and they vanish from
                      state/local portals after award.
    2 spec book    -- project manuals. Where basis-of-design is declared.
    3 mep drawings -- equipment schedules carry BOD in a second form.
    4 drawings     -- architectural/structural sheet sets.
    5 other        -- bid forms, wage determinations, cover sheets.

WHY FILENAME ALONE IS NOT ENOUGH (Amendment II, D1). SAM.gov and municipal
portals routinely serve `Attachment_A.pdf`, `Doc_001.pdf`, `Amd_1.pdf`. A
download cap applied on filename regex drops real addenda while keeping a
cover sheet called `Specification_Notice.pdf`, and the loss is permanent
because the file is never fetched. So classification is two-phase:

    classify_name()  -- cheap, from filename/description
    classify_text()  -- from the first page, for anything the name left as
                        UNKNOWN or 'other'

and the cap is applied only AFTER the text phase. classify_name() returning
`other` is treated as "not yet known", never as "confirmed low value".

WHY ADDENDA ALSO GET SPEC TREATMENT (Amendment II, D2). Addenda routinely
rewrite whole sections -- "Delete Section 23 05 00 and replace with the
attached." So `wants_spec_extraction()` is true for addenda as well as spec
books, and it is ADDITIVE: every document still gets page text, because
document_pages feeds pgvector and FTS and the best documents must not be
missing from search.
"""
from __future__ import annotations

import re

ADDENDA = "addenda"
SPEC_BOOK = "spec_book"
MEP_DRAWINGS = "mep_drawings"
DRAWINGS = "drawings"
OTHER = "other"
UNKNOWN = "unknown"

RANK = {ADDENDA: 1, SPEC_BOOK: 2, MEP_DRAWINGS: 3, DRAWINGS: 4, OTHER: 5, UNKNOWN: 4}

# --- filename / description signals -----------------------------------------
# Ordered: first match wins, so the highest-value interpretation is taken.
_NAME_RULES: list[tuple[str, str]] = [
    # `\bamd\b` does NOT match "Amd_1.pdf": underscore is a word character, so
    # there is no boundary between "d" and "_". Caught by the classifier's own
    # test -- and it is exactly the D1 failure mode, since the file would have
    # been ranked 5 and dropped by the cap. Use an explicit separator class.
    (ADDENDA,      r"addend|amend|(?:^|[\s_.\-])amd(?:[\s_.\-]|\d|$)"
                   r"|pre[\s_-]?bid|\bq\s*&\s*a\b|question.*answer|clarification"),
    (SPEC_BOOK,    r"specification|specsasone|project[\s_-]*manual|tech(nical)?[\s_-]*spec"
                   r"|\bspecs?\b|division[\s_-]*\d{2}|\b\d{2}[\s_-]\d{2}[\s_-]\d{2}\b"),
    (MEP_DRAWINGS, r"\bmep\b|mechanical|electrical|plumbing|\bhvac\b|fire[\s_-]?protection"
                   r"|\bm-?\d{3}\b|\be-?\d{3}\b|\bp-?\d{3}\b"),
    (DRAWINGS,     r"drawing|plan[\s_-]?set|\bsheet\b|blueprint|\bdwg\b|architectural|structural|\bplans?\b"),
    (OTHER,        r"wage|davis[\s_-]?bacon|\bsf-?\d+\b|past[\s_-]?performance|invoice|receipt"
                   r"|cover[\s_-]?(sheet|letter)|attendance|transcript|sign[\s_-]?in"),
]

# --- first-page text signals ------------------------------------------------
# Stronger evidence than a filename, so these override a name-based guess.
# Deliberately specific: a bare word like "specification" appears on the cover
# of nearly every bid document and is not a signature.
_TEXT_RULES: list[tuple[str, str]] = [
    (ADDENDA,      r"addendum\s*(no\.?|number|#)?\s*\d|amendment\s*(no\.?|#)?\s*\d"
                   r"|the\s+following\s+changes\s+are\s+made|pre[\s-]?bid\s+(meeting|conference)"
                   r"|substitution\s+request"),
    (SPEC_BOOK,    r"\bsection\s+\d{2}\s?\d{2}\s?\d{2}\b|part\s+1\s*[-–—]?\s*general"
                   r"|basis\s+of\s+design|table\s+of\s+contents.*division|approved\s+manufacturers?"),
    (MEP_DRAWINGS, r"equipment\s+schedule|mechanical\s+schedule|electrical\s+(panel|riser)"
                   r"|\bcfm\b.*\bton(s)?\b|panelboard\s+schedule"),
]

# What a first page must contain to be worth spec-book extraction at all.
SPEC_STRUCTURE_RE = re.compile(
    r"\bsection\s+\d{2}\s?\d{2}\s?\d{2}\b|part\s+[123]\s*[-–—]\s*(general|products|execution)"
    r"|basis\s+of\s+design|approved\s+manufacturers?", re.I)


def classify_name(name: str, description: str = "") -> str:
    """Cheap first pass. Returns UNKNOWN rather than OTHER when nothing
    matches -- 'no signal' and 'confirmed low value' must not be conflated,
    because the cap treats them differently."""
    blob = f"{name} {description}"
    for label, pat in _NAME_RULES:
        if re.search(pat, blob, re.I):
            return label
    return UNKNOWN


def classify_text(first_page: str) -> str:
    """Second pass over real page-1 text. Stronger than the filename."""
    if not first_page:
        return UNKNOWN
    head = first_page[:6000]
    for label, pat in _TEXT_RULES:
        if re.search(pat, head, re.I):
            return label
    return UNKNOWN


def classify(name: str, description: str = "", first_page: str = "") -> str:
    """Combined verdict. Text evidence WINS over the filename when the two
    disagree -- `Attachment_A.pdf` whose first page reads "ADDENDUM NO. 3" is
    an addendum, whatever it is called."""
    by_text = classify_text(first_page) if first_page else UNKNOWN
    if by_text != UNKNOWN:
        return by_text
    by_name = classify_name(name, description)
    return by_name if by_name != UNKNOWN else OTHER


def rank_of(label: str) -> int:
    return RANK.get(label, RANK[UNKNOWN])


def wants_spec_extraction(label: str, first_page: str = "") -> bool:
    """Should extract-spec-book.py run on this, IN ADDITION to page text?

    True for spec books AND addenda (addenda rewrite whole sections), and for
    anything whose page text shows MasterFormat structure regardless of its
    file-level label -- structure on the page is better evidence than the
    class we assigned to the file.
    """
    if label in (SPEC_BOOK, ADDENDA):
        return True
    return bool(first_page and SPEC_STRUCTURE_RE.search(first_page[:6000]))


def apply_cap(items: list[dict], cap: int, key: str = "doc_class") -> tuple[list[dict], list[dict]]:
    """Keep the highest-value `cap` items; return (kept, dropped).

    Stable within a rank so ordering stays deterministic across runs -- a
    non-deterministic cap would make two runs of the same source disagree
    about which documents exist.
    """
    if cap <= 0 or len(items) <= cap:
        return items, []
    ordered = sorted(enumerate(items), key=lambda p: (rank_of(p[1].get(key, UNKNOWN)), p[0]))
    keep_idx = {i for i, _ in ordered[:cap]}
    return ([it for i, it in enumerate(items) if i in keep_idx],
            [it for i, it in enumerate(items) if i not in keep_idx])
