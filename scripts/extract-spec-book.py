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
  python3 scripts/extract-spec-book.py --pdf gs://specindex-ai-raw-documents/specbook.pdf \\
      --project-id ga-... --write-bq

--write-bq loads spec_extractions and citations into the `warehouse` BigQuery
dataset (see scripts/test-gcp-storage-bq.py for the schema these were smoke
tested against). entity_resolution is NOT written here — that table maps raw
manufacturer mentions to a canonical name/product, and no canonicalization
logic exists yet anywhere in this pipeline. Writing to it now would mean
putting unresolved raw strings in a table whose whole purpose is to hold
resolved ones; leave it empty until that logic is actually built.

Note: --write-bq uses streaming inserts (no upsert) — re-running against the
same PDF will duplicate rows in BigQuery, unlike --write-db which replaces
cleanly. Fine for a first wiring pass; revisit if this becomes a re-run path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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

# A section HEADING -- "SECTION 23 21 13" at the start of a line. This is the
# only reliable start marker. Bare code mentions are not: they appear in the
# table of contents, in cross-references, and repeated in every page's running
# header, which is what defeated two earlier attempts (189 page-fragments, then
# 12 collapsed header-runs, on a book that actually holds 10 sections).
SECTION_HEADING_RE = re.compile(
    r"^\s*SECTION\s+(\d{2})\s?(\d{2})\s?(\d{2})\b", re.IGNORECASE | re.MULTILINE
)

# CSI three-part format: a real section opens with PART 1 GENERAL. Requiring it
# alongside the heading discriminates a section START from a page that merely
# cites the section number.
PART_ONE_RE = re.compile(r"PART\s*1\b|^\s*1\.\s*GENERAL", re.IGNORECASE | re.MULTILINE)

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
    """Group pages into real MasterFormat SECTIONS, one per "SECTION nn nn nn".

    Three attempts, measured on a real 204-page VA project manual
    (Renovate Building 9A, Carl Vinson VAMC, SAM.gov notice 198ed58de2ca4273):

      * Split on any page mentioning one division -> **189** "sections", 44 of
        them Division 01. Each was a page fragment, so the model was asked
        "what is the basis of design here?" about submittal boilerplate. Found
        2 manufacturers and ZERO substitution clauses.
      * Split on any bare section code -> **12**. Bare codes repeat in every
        page's running header, so consecutive-run collapsing swallowed whole
        sections.
      * Split on the "SECTION nn nn nn" HEADING, confirmed by PART 1 on the
        same page -> **10**, matching the book's actual contents.

    The lesson worth keeping: a bare code mention is not a section start. It
    appears in the table of contents, in cross-references, and in the running
    header of every page of a DIFFERENT section.

    Pages before the first heading (cover, TOC, front matter) are dropped.
    """
    hits: list[tuple[int, str]] = []
    for i, text in enumerate(pages):
        m = SECTION_HEADING_RE.search(text)
        if not m:
            continue
        if not PART_ONE_RE.search(text):
            # Heading without PART 1 -- a cross-reference or continuation page,
            # not a section start.
            continue
        division = m.group(1)
        if division not in CSI_DIVISIONS:
            continue
        code = f"{m.group(1)} {m.group(2)} {m.group(3)}"
        if hits and hits[-1][1] == code:
            continue
        hits.append((i, code))

    if not hits:
        return _find_division_sections_by_division(pages)

    sections: list[DivisionSection] = []
    for idx, (page_no, code) in enumerate(hits):
        end_page = hits[idx + 1][0] - 1 if idx + 1 < len(hits) else len(pages) - 1
        end_page = max(end_page, page_no)
        sections.append(
            DivisionSection(
                division=code.split()[0],
                start_page=page_no,
                end_page=end_page,
                text="\n".join(pages[page_no : end_page + 1]),
            )
        )
    return sections


def _find_division_sections_by_division(pages: list[str]) -> list[DivisionSection]:
    """Original division-level segmentation, kept as a fallback for books that
    carry no MasterFormat section numbers at all."""
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
        sections.append(
            DivisionSection(
                division=division,
                start_page=page_no,
                end_page=end_page,
                text="\n".join(pages[page_no : end_page + 1]),
            )
        )
    return sections


def _gemini_schema(node):
    """Adapt the Anthropic-style JSON Schema in EXTRACTION_TOOL for Vertex/Gemini.

    Anthropic accepts a UNION type -- {"type": ["string", "null"]} -- which is how
    the optional fields here are declared. Gemini's Schema rejects that outright
    (pydantic: "Input should be 'STRING'... input_value=['string','null']") and
    wants a single type plus nullable=True.

    Converting here rather than rewriting EXTRACTION_TOOL keeps that constant as
    the single readable description of the output shape, and keeps the door open
    if the classification pass ever moves again.
    """
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key == "type" and isinstance(value, list):
            non_null = [v for v in value if v != "null"]
            out["type"] = (non_null[0] if non_null else "string").upper()
            if "null" in value:
                out["nullable"] = True
        elif key == "type" and isinstance(value, str):
            out["type"] = value.upper()
        elif key in ("properties", "items"):
            out[key] = ({k: _gemini_schema(v) for k, v in value.items()}
                        if key == "properties" else _gemini_schema(value))
        elif key in ("description", "required", "enum", "nullable"):
            out[key] = value
        # Anything else (additionalProperties, $schema, ...) is dropped: Gemini
        # errors on unknown keys rather than ignoring them.
    return out


PART_TWO_RE = re.compile(r"PART\s*2\b|^\s*2\.\s*PRODUCTS", re.IGNORECASE | re.MULTILINE)
MODEL_CHAR_BUDGET = 12000
SCOPE_CHARS = 2000


def section_text_for_model(text: str) -> str:
    """Send the model the part of the section that actually holds the answer.

    Naively truncating to the first 12,000 chars loses the manufacturer list on
    long sections, because PART 2 PRODUCTS -- where basis-of-design products and
    "acceptable manufacturers" are named -- sits after PART 1 GENERAL, which is
    pages of submittal and quality-assurance boilerplate.

    Measured on a real VA project manual (2026-08-04): of 10 sections, 6 exceed
    the window, and for section 23 09 23 PART 2 begins at char 45,141 and for
    28 31 00 at char 19,327. Both manufacturer lists were entirely invisible to
    the model -- a silent recall loss that looks exactly like "this section
    names no manufacturers".

    So: keep the opening for section identity and scope, then jump to PART 2 and
    spend the rest of the budget there.
    """
    if len(text) <= MODEL_CHAR_BUDGET:
        return text
    m = PART_TWO_RE.search(text)
    if not m:
        return text[:MODEL_CHAR_BUDGET]
    head = text[:SCOPE_CHARS]
    products = text[m.start() : m.start() + (MODEL_CHAR_BUDGET - SCOPE_CHARS)]
    return f"{head}\n\n[... PART 1 GENERAL abridged ...]\n\n{products}"


SECTION_PROMPT = (
    "You are extracting basis-of-design and approved-manufacturer data from "
    "CSI MasterFormat Division {division} ({division_name}) of a construction "
    "specification book. Only extract facts EXPLICITLY stated in the text below "
    "-- do not infer manufacturers or products that aren't named. An invented "
    "manufacturer here is worse than a missing one: every fact this produces is "
    "shown to a customer with a page citation, so a fabricated name is directly "
    "visible as a lie.\n\n"
    "Basis of design means the specific manufacturer and model the design was "
    "built around -- usually introduced as 'basis of design', 'BOD', or a named "
    "product in a schedule. Approved manufacturers are the 'or equal' / "
    "'acceptable manufacturers' list. These are DIFFERENT: being basis of design "
    "is far stronger than being an acceptable alternate, and the distinction is "
    "the whole point of this extraction. If a name appears only in an acceptable "
    "list, it is NOT the basis of design.\n\n"
    "If nothing relevant is stated, return empty arrays and confidence 'low'.\n\n"
    "--- SECTION TEXT ---\n{text}"
)


def classify_section(client, section: DivisionSection, model: str) -> dict:
    """Extract one division section via Vertex/Gemini structured output.

    Ported from Anthropic tool-use 2026-08-04. The rest of this pipeline
    (enrich-project-details.py, gemini_discovery_chat.py) already runs on
    Vertex, and ANTHROPIC_API_KEY was never configured here -- so this script
    was the only thing in the repo that could not run at all. One stray
    credential dependency is how a pipeline rots; there is now none.

    Gemini's response_schema gives the same guarantee Anthropic's forced
    tool_choice did: a JSON object matching EXTRACTION_TOOL's shape, so the
    caller's field access is unchanged.
    """
    from google.genai import types  # noqa: PLC0415

    prompt = SECTION_PROMPT.format(
        division=section.division,
        division_name=CSI_DIVISIONS[section.division],
        text=section_text_for_model(section.text),
    )
    schema = _gemini_schema(EXTRACTION_TOOL["input_schema"])
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0,  # extraction, not generation -- never sample here
        ),
    )
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Model returned an empty response")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model did not return valid JSON: {e}: {text[:200]}") from e


def download_from_gcs(gcs_uri: str) -> Path:
    """Download a gs://bucket/path.pdf URI to a local temp file and return its path."""
    from google.cloud import storage

    bucket_name, _, blob_path = gcs_uri.removeprefix("gs://").partition("/")
    if not blob_path:
        raise SystemExit(f"Invalid GCS URI (expected gs://bucket/path.pdf): {gcs_uri}")

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    client = storage.Client()
    client.bucket(bucket_name).blob(blob_path).download_to_filename(tmp.name)
    print(f"Downloaded {gcs_uri} -> {tmp.name}", file=sys.stderr)
    return Path(tmp.name)


def run(pdf_path: Path, project_id: str, dry_run: bool, model: str, source_document: str) -> list[DivisionExtraction]:
    pages = extract_pages(pdf_path)
    sections = find_division_sections(pages)

    if not sections:
        print(f"No CSI division headers detected in {source_document} — nothing to extract.", file=sys.stderr)
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
                source_document=source_document,
                page=s.start_page + 1,
                confidence="unclassified (dry-run)",
            )
            for s in sections
        ]

    from google import genai  # noqa: PLC0415

    sys.path.insert(0, str(Path(__file__).resolve().parent / "state_agent_pipeline"))
    from config import Settings  # noqa: PLC0415

    settings = Settings.from_env()
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )
    # Never hardcode a model version here. config.py already carries the repo's
    # current Flash model and is the one place to change it; pasting a literal
    # is how this file ended up on a superseded version in the first place.
    # Step 9. PRO, not Flash: this parses MasterFormat divisions and decides
    # basis-of-design vs listed alternate, and NOTHING downstream re-checks it
    # -- the output is the product. See specindex/models.py.
    if model is None:
        try:
            from specindex import models as _m  # noqa: PLC0415
            model = _m.model_for_step(9, settings)
        except Exception:  # noqa: BLE001 -- routing must never break extraction
            model = getattr(settings, "pro_model", settings.flash_model)
    print(f"[spec-book] classifying with {model}", file=sys.stderr)

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
                source_document=source_document,
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


CONFIDENCE_SCORES = {"high": 0.9, "medium": 0.6, "low": 0.3}


def write_bq(project_id: str, payload: dict, bq_project: str, dataset: str) -> None:
    """Stream extraction + citation rows into the warehouse dataset. See module
    docstring for why entity_resolution is intentionally not written here."""
    from google.cloud import bigquery

    client = bigquery.Client(project=bq_project)
    now = datetime.now(timezone.utc).isoformat()

    extraction_rows = []
    citation_rows = []
    for d in payload["csi_divisions"]:
        extraction_id = str(uuid.uuid4())
        confidence_score = CONFIDENCE_SCORES.get(d["confidence"])
        extraction_rows.append(
            {
                "extraction_id": extraction_id,
                "project_id": project_id,
                "source_document": d["source_document"],
                "csi_division": d["division"],
                "csi_section": None,
                "product_category": None,
                "basis_of_design_product": d["basis_of_design_product"],
                "approved_manufacturers": "; ".join(d["approved_manufacturers"]) or None,
                "substitution_language": d["substitution_language"],
                "confidence_score": confidence_score,
                "extracted_at": now,
            }
        )
        citation_rows.append(
            {
                "citation_id": str(uuid.uuid4()),
                "extraction_id": extraction_id,
                "source_document": d["source_document"],
                "page_number": d["page"],
                "source_snippet": None,
                "confidence_score": confidence_score,
            }
        )

    errors = client.insert_rows_json(f"{bq_project}.{dataset}.spec_extractions", extraction_rows)
    if errors:
        raise RuntimeError(f"BigQuery insert into spec_extractions failed: {errors}")
    errors = client.insert_rows_json(f"{bq_project}.{dataset}.citations", citation_rows)
    if errors:
        raise RuntimeError(f"BigQuery insert into citations failed: {errors}")

    print(
        f"Wrote {len(extraction_rows)} extraction row(s) and {len(citation_rows)} citation row(s) "
        f"to {bq_project}.{dataset}",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", required=True, help="Path to spec book PDF, or a gs://bucket/path.pdf URI")
    parser.add_argument("--project-id", required=True, help="SpecIndex project_id this spec book belongs to")
    parser.add_argument("--model", default=None,
                        help="Vertex/Gemini model for the classification pass. "
                             "Defaults to the step-9 model (Gemini Pro) via specindex/models.py "
                             "rather than a literal, so it tracks the repo's configured model "
                             "instead of going stale here. Flash is the right class: this is "
                             "structured extraction from text that already contains the answer, "
                             "not reasoning.")
    parser.add_argument("--dry-run", action="store_true", help="Parse/chunk only, skip the LLM call")
    parser.add_argument("--write-db", action="store_true", help="Write results into the live projects table")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "postgresql://specindex:specindex@localhost:5432/specindex"),
        help="Postgres connection string (used only with --write-db)",
    )
    parser.add_argument("--write-bq", action="store_true", help="Stream results into the warehouse BigQuery dataset")
    parser.add_argument("--bq-project", default="specindex-ai", help="GCP project for --write-bq")
    parser.add_argument("--bq-dataset", default="warehouse", help="BigQuery dataset for --write-bq")
    parser.add_argument("--out", type=Path, help="Write JSON output to this path (default: stdout)")
    args = parser.parse_args()

    downloaded_tmp_path: Path | None = None
    if args.pdf.startswith("gs://"):
        source_document = args.pdf
        pdf_path = download_from_gcs(args.pdf)
        downloaded_tmp_path = pdf_path
    else:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            raise SystemExit(f"PDF not found: {pdf_path}")
        source_document = pdf_path.name

    try:
        extractions = run(pdf_path, args.project_id, dry_run=args.dry_run, model=args.model, source_document=source_document)
    finally:
        if downloaded_tmp_path is not None:
            downloaded_tmp_path.unlink(missing_ok=True)

    payload = to_json(extractions)
    payload["project_id"] = args.project_id

    output = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(output)
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(output)

    if args.dry_run and (args.write_db or args.write_bq):
        raise SystemExit("--write-db/--write-bq and --dry-run are mutually exclusive")
    if args.write_db:
        write_db(args.project_id, payload, args.database_url)
    if args.write_bq:
        write_bq(args.project_id, payload, args.bq_project, args.bq_dataset)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
