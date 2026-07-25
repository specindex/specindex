#!/usr/bin/env python3
"""Extract cited CSI MasterFormat division data from a construction spec book PDF.

Implements the pipeline described in docs/CONTEXT.md ("Sourcing Layer" section)
and writes output matching the csi_division_codes / csi_divisions columns added
in db/migrations/002_schema_v2.sql (see docs/DATA_SCHEMA_V2.md).

Pipeline:
  1. Deterministic text extraction per page (PyMuPDF) — no OCR/vision LLM tokens
     burned unless the PDF is a scanned raster (detected and reported, not handled).
  2. Group pages into CSI division sections via section-header pattern matching
     (e.g. "DIVISION 23", "23 00 00").
  3. One structured-extraction LLM call per detected division section, forced to
     JSON via tool-use, pulling basis-of-design product, approved manufacturers,
     "or equal" substitution language, and model numbers.
  4. Every extracted fact carries a page citation back to the source PDF — this
     is load-bearing: an unverifiable "your competitor is specified here" claim
     burns SpecIndex's credibility with manufacturers, so nothing here should be
     un-cited.

Status as of 2026-07-25: built and unit-tested against a synthetic sample PDF
(no real spec book was available in this environment). The PDF-parsing and
section-detection layer is deterministic and verified working end-to-end. The
LLM classification layer requires ANTHROPIC_API_KEY, which is not configured in
this environment — it has NOT been exercised against a live API call. Run
`python3 scripts/extract-spec-book.py --pdf <sample.pdf> --project-id <id> --dry-run`
to test extraction/chunking without calling the API.

Usage:
  python3 scripts/extract-spec-book.py --pdf specbook.pdf --project-id ga-alpharetta-bc250259
  python3 scripts/extract-spec-book.py --pdf specbook.pdf --project-id ga-... --write-db
  python3 scripts/extract-spec-book.py --pdf specbook.pdf --project-id ga-... --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]

# CSI MasterFormat 2020 division titles (00-49). Public, standardized reference
# data — not something the LLM should be asked to invent per project.
CSI_DIVISIONS = {
    "00": "Procurement and Contracting Requirements",
    "01": "General Requirements",
    "02": "Existing Conditions",
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood, Plastics, and Composites",
    "07": "Thermal and Moisture Protection",
    "08": "Openings",
    "09": "Finishes",
    "10": "Specialties",
    "11": "Equipment",
    "12": "Furnishings",
    "13": "Special Construction",
    "14": "Conveying Equipment",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "Heating, Ventilating, and Air Conditioning (HVAC)",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety and Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "34": "Transportation",
    "35": "Waterway and Marine Construction",
    "40": "Process Integration",
    "41": "Material Processing and Handling Equipment",
    "42": "Process Heating, Cooling, and Drying Equipment",
    "43": "Process Gas and Liquid Handling, Purification, and Storage Equipment",
    "44": "Pollution and Waste Control Equipment",
    "45": "Industry-Specific Manufacturing Equipment",
    "46": "Water and Wastewater Equipment",
    "48": "Electrical Power Generation",
}

# Matches "DIVISION 23", "DIVISION 23 -", "23 00 00", "SECTION 23 00 00" etc.,
# anchored at the start of a line so mid-sentence cross-references to other
# divisions/sections (e.g. "per Section 01 25 00", "coordinate with Division 26")
# don't get mistaken for a new section header.
DIVISION_HEADER_RE = re.compile(
    r"^\s*(?:DIVISION\s+(\d{2})\b)|^\s*(?:SECTION\s+)?(\d{2})\s?\d{2}\s?\d{2}\b",
    re.IGNORECASE | re.MULTILINE,
)

EXTRACTION_TOOL = {
    "name": "record_division_extraction",
    "description": (
        "Record basis-of-design and approved-manufacturer data extracted from "
        "one CSI MasterFormat division section of a construction spec book."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "division": {"type": "string", "description": "Two-digit CSI division number, e.g. '23'"},
            "basis_of_design_product": {"type": ["string", "null"]},
            "approved_manufacturers": {"type": "array", "items": {"type": "string"}},
            "substitution_language": {"type": ["string", "null"], "description": "Verbatim or close paraphrase of 'or equal' / substitution clause, if present"},
            "model_numbers": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["division", "approved_manufacturers", "model_numbers", "confidence"],
    },
}


@dataclass
class DivisionSection:
    division: str
    start_page: int  # 0-indexed
    end_page: int
    text: str


@dataclass
class DivisionExtraction:
    division: str
    division_name: str
    basis_of_design_product: str | None
    approved_manufacturers: list[str]
    substitution_language: str | None
    model_numbers: list[str]
    source_document: str
    page: int  # 1-indexed, for human citation
    confidence: str


def extract_pages(pdf_path: Path) -> list[str]:
    """Return per-page extracted text. Raises if the PDF looks like a raster scan
    with no embedded text layer (out of scope for this pipeline — see docs/CONTEXT.md,
    scanned drawings/spec books need vision-LLM handling, not this deterministic path)."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    total_chars = sum(len(p.strip()) for p in pages)
    if total_chars < 50 * len(pages):
        raise ValueError(
            f"{pdf_path} looks like a scanned/raster PDF (avg {total_chars // max(len(pages),1)} "
            "chars/page of extractable text). This pipeline only handles vector-text spec books — "
            "see docs/CONTEXT.md 'Engineering Drawings' section for the scanned-document path."
        )
    return pages


def find_division_sections(pages: list[str]) -> list[DivisionSection]:
    """Group pages into division sections by locating division headers.
    Pages before the first detected header are dropped (front matter / TOC).

    A page that mentions 2+ distinct divisions is treated as a table-of-contents
    or summary listing, not a section start, and skipped — a real section page
    is about one division; a TOC page lists several in quick succession."""
    hits: list[tuple[int, str]] = []
    for i, text in enumerate(pages):
        divisions_on_page = {
            (m.group(1) or m.group(2))
            for m in DIVISION_HEADER_RE.finditer(text)
            if (m.group(1) or m.group(2)) in CSI_DIVISIONS
        }
        if len(divisions_on_page) == 1:
            hits.append((i, next(iter(divisions_on_page))))

    if not hits:
        return []

    sections: list[DivisionSection] = []
    for idx, (page_no, division) in enumerate(hits):
        end_page = hits[idx + 1][0] - 1 if idx + 1 < len(hits) else len(pages) - 1
        end_page = max(end_page, page_no)
        text = "\n".join(pages[page_no : end_page + 1])
        sections.append(DivisionSection(division=division, start_page=page_no, end_page=end_page, text=text))
    return sections


def classify_section(client, section: DivisionSection, model: str) -> dict:
    prompt = (
        f"You are extracting basis-of-design and approved-manufacturer data from "
        f"CSI MasterFormat Division {section.division} ({CSI_DIVISIONS[section.division]}) "
        "of a construction specification book. Only extract facts explicitly stated in "
        "the text below — do not infer manufacturers or products that aren't named. "
        "If nothing relevant is stated, return empty arrays and confidence 'low'.\n\n"
        f"--- SECTION TEXT ---\n{section.text[:12000]}"
    )
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_division_extraction"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Model did not return a tool_use block")


def run(pdf_path: Path, project_id: str, dry_run: bool, model: str) -> list[DivisionExtraction]:
    pages = extract_pages(pdf_path)
    sections = find_division_sections(pages)

    if not sections:
        print(f"No CSI division headers detected in {pdf_path.name} — nothing to extract.", file=sys.stderr)
        return []

    print(f"Found {len(sections)} division section(s): {[s.division for s in sections]}", file=sys.stderr)

    if dry_run:
        print("--dry-run: skipping LLM classification, parsing/chunking only.", file=sys.stderr)
        return [
            DivisionExtraction(
                division=s.division,
                division_name=CSI_DIVISIONS[s.division],
                basis_of_design_product=None,
                approved_manufacturers=[],
                substitution_language=None,
                model_numbers=[],
                source_document=pdf_path.name,
                page=s.start_page + 1,
                confidence="unclassified (dry-run)",
            )
            for s in sections
        ]

    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set. Use --dry-run to test parsing without the LLM pass.")
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for section in sections:
        data = classify_section(client, section, model)
        results.append(
            DivisionExtraction(
                division=data["division"],
                division_name=CSI_DIVISIONS.get(data["division"], "Unknown"),
                basis_of_design_product=data.get("basis_of_design_product"),
                approved_manufacturers=data.get("approved_manufacturers", []),
                substitution_language=data.get("substitution_language"),
                model_numbers=data.get("model_numbers", []),
                source_document=pdf_path.name,
                page=section.start_page + 1,
                confidence=data.get("confidence", "low"),
            )
        )
    return results


def to_json(extractions: list[DivisionExtraction]) -> dict:
    return {
        "csi_division_codes": sorted({int(e.division) for e in extractions}),
        "csi_divisions": [
            {
                "division": e.division,
                "division_name": e.division_name,
                "basis_of_design_product": e.basis_of_design_product,
                "approved_manufacturers": e.approved_manufacturers,
                "substitution_language": e.substitution_language,
                "model_numbers": e.model_numbers,
                "source_document": e.source_document,
                "page": e.page,
                "confidence": e.confidence,
            }
            for e in extractions
        ],
    }


def write_db(project_id: str, payload: dict, database_url: str) -> None:
    """Write results into project_csi_divisions (one row per division, FK'd to
    projects.project_sk — see db/migrations/003_csi_divisions_table.sql) and
    refresh the projects.csi_division_codes summary array.

    Re-running against the same PDF replaces that document's rows cleanly:
    existing rows for (project_sk, source_document) are deleted first, so a
    re-processed spec book doesn't leave stale divisions behind."""
    import psycopg2

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT project_sk FROM projects WHERE project_id = %s", (project_id,))
    row = cur.fetchone()
    if row is None:
        raise SystemExit(f"No project found with project_id={project_id!r} — not written.")
    project_sk = row[0]

    divisions = payload["csi_divisions"]
    source_documents = {d["source_document"] for d in divisions}
    for source_document in source_documents:
        cur.execute(
            "DELETE FROM project_csi_divisions WHERE project_sk = %s AND source_document = %s",
            (project_sk, source_document),
        )

    for d in divisions:
        cur.execute(
            """
            INSERT INTO project_csi_divisions (
              project_sk, division, division_name, basis_of_design_product,
              approved_manufacturers, substitution_language, model_numbers,
              source_document, page, confidence
            ) VALUES (
              %(project_sk)s, %(division)s, %(division_name)s, %(basis_of_design_product)s,
              %(approved_manufacturers)s, %(substitution_language)s, %(model_numbers)s,
              %(source_document)s, %(page)s, %(confidence)s
            )
            ON CONFLICT (project_sk, division, source_document, page) DO UPDATE SET
              division_name = EXCLUDED.division_name,
              basis_of_design_product = EXCLUDED.basis_of_design_product,
              approved_manufacturers = EXCLUDED.approved_manufacturers,
              substitution_language = EXCLUDED.substitution_language,
              model_numbers = EXCLUDED.model_numbers,
              confidence = EXCLUDED.confidence
            """,
            {**d, "project_sk": project_sk},
        )

    # Denormalized summary array on the project row for cheap "does this
    # project touch division X" filtering without a join.
    cur.execute(
        """
        UPDATE projects
        SET csi_division_codes = (
              SELECT COALESCE(array_agg(DISTINCT division::smallint), '{}')
              FROM project_csi_divisions WHERE project_sk = %(project_sk)s
            ),
            last_updated_at = now()
        WHERE project_sk = %(project_sk)s
        """,
        {"project_sk": project_sk},
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"Wrote {len(divisions)} division record(s) to project_id={project_id} (project_sk={project_sk})", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, type=Path, help="Path to spec book PDF")
    parser.add_argument("--project-id", required=True, help="SpecIndex project_id this spec book belongs to")
    parser.add_argument("--model", default="claude-sonnet-5", help="Anthropic model for the classification pass")
    parser.add_argument("--dry-run", action="store_true", help="Parse/chunk only, skip the LLM call")
    parser.add_argument("--write-db", action="store_true", help="Write results into the live projects table")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
        help="Postgres connection string (used only with --write-db)",
    )
    parser.add_argument("--out", type=Path, help="Write JSON output to this path (default: stdout)")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    extractions = run(args.pdf, args.project_id, dry_run=args.dry_run, model=args.model)
    payload = to_json(extractions)
    payload["project_id"] = args.project_id

    output = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(output)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(output)

    if args.write_db:
        if args.dry_run:
            raise SystemExit("--write-db and --dry-run are mutually exclusive")
        write_db(args.project_id, payload, args.database_url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
