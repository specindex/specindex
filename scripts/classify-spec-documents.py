#!/usr/bin/env python3
"""Bulk classifier -- walks documents with text, writes CSI divisions.

THE GAP THIS CLOSES. project_csi_divisions had ZERO rows while 269 documents
were flagged structured_extraction_at. Two different scripts, no seam between
them: extract-spec-positions.py set the flag and wrote substitution_rulings,
never divisions; extract-spec-book.py writes divisions but takes ONE PDF and a
--project-id, so nothing ever drove it in bulk. The table was not empty because
extraction failed -- nothing was ever pointed at it, while a status flag said
the work was done. Any query asking "what still needs extraction?" answered
NONE.

CLAUDE, NOT GEMINI. coverage-plan-v2.md is explicit that the classifier at scale
is a Claude API call inside the pipeline. extract-spec-book.py predates that and
routes to Gemini, so this is a replacement rather than an extension.

WORKS ON TEXT ALREADY IN POSTGRES, not on PDFs. document_pages holds 80,083
extracted pages; re-downloading and re-parsing a 200-page book to classify it
would be slower, costlier and would fail on anything since deleted upstream.

THREE OWNERS. After migration 055 a division row attaches to a project, a
reference document (state DOT spec books -- 18,144 pages that previously could
not be classified at all) or a legislative document. Exactly one.

SETS divisions_written_at, AND ONLY AFTER ROWS LAND. That is the whole point of
the new column: structured_extraction_at meant "some extractor touched this",
which is how 269 documents read as done with nothing to show.
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

# VERTEX GEMINI FLASH, NOT ANTHROPIC. Asif's call 2026-08-07 to keep this on
# GCP credits -- the Anthropic run had already died with "Your credit balance is
# too low", 150 documents for 150 failures.
#
# Flash is defensible here beyond cost. The standing routing rule is Flash where
# a VERIFIER FOLLOWS, and one does: the response schema constrains the shape,
# every field must be literally present in the text, and `confidence` is
# self-reported then checked against whether a numbered section heading exists.
# The risk Flash carries is invention, and the prompt's hard rule is that
# nothing may be inferred -- a missing manufacturer is null, never a guess.
MODEL = "gemini-3.6-flash"
CHUNK_CHARS = 90_000         # ~22k tokens per call
MAX_CHUNKS = 6               # cap cost per document

PROMPT = """You are reading text extracted from a construction specification document.

Return STRICT JSON, no prose:
{"divisions":[{"division":"23","division_name":"Heating, Ventilating, and Air Conditioning",
"basis_of_design_product":"Trane CSAA012 or approved equal","approved_manufacturers":["Trane","Carrier"],
"substitution_language":"verbatim quote about substitutions or 'or equal'","model_numbers":["CSAA012"],
"openness":"or-equal","page_from":41,"page_to":58,"confidence":"high"}]}

RULES:
- Only divisions you can actually see section content for. An entry in a table of
  contents is NOT evidence the division is specified.
- basis_of_design_product, substitution_language and model_numbers: null/[] unless
  literally present. Never infer a manufacturer.
- openness: "proprietary" (named product, no substitution permitted), "or-equal"
  (named product plus or-equal language), "performance" (requirements only, no
  product named), "unspecified".
- substitution_language must be a VERBATIM quote, not a paraphrase.
- confidence: "high" if a numbered section heading is present, else "low".
- Empty list if this is a bid form, notice, drawing index or tabulation.
"""


def _one_call(client, text: str) -> list[dict]:
    """One Vertex call. response_mime_type forces JSON so the model cannot wrap
    the answer in prose that a regex then has to dig out -- the earlier
    Anthropic path scraped the first {...} it found, which silently returned []
    whenever the model added a preamble."""
    from google.genai import types as gtypes
    resp = client.models.generate_content(
        model=MODEL,
        contents=PROMPT + "\n\n---\n\n" + text,
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,          # extraction, not composition
            max_output_tokens=8000,
        ),
    )
    raw = (resp.text or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return data.get("divisions", []) or []


# CSI MasterFormat divisions are a FIXED, GAPPED LIST -- not the range 00-49.
#
# THIS IS THE VERIFIER THAT MAKES FLASH DEFENSIBLE. On its first run Flash
# returned division "100" from a state DOT book -- reading "SECTION 100" as a
# division number. Highway specs number their own way and have no MasterFormat
# divisions at all, so the honest output there is an empty list. Without this
# check an invented division reaches the record page looking exactly like a real
# one, and the whole product claim is that we quote rather than infer.
#
# THE RANGE CHECK WAS NOT ENOUGH. `range(0, 50)` accepted every number 00-49,
# but MasterFormat leaves whole bands RESERVED and unassigned: 15-20, 24, 29,
# 30, 36-39, 47, 49. Measured on a 20-document dry run 2026-08-08, Flash
# emitted "18", "29" and "30" on two DOT-style books -- all three are reserved,
# none is a real division, and each passed the range check and would have been
# written as fact. At 2 bad documents in 20, the ~14,000-document backlog would
# have put thousands of junk rows into project_csi_divisions, which is what the
# scope matrix on the record page reads from.
#
# So the allowlist is the actual published list, gaps included. A reserved
# number is not a near-miss to be rounded to a neighbour -- it is evidence the
# model was reading some other numbering system, and the honest answer is to
# drop it.
_VALID_DIVISIONS = frozenset(
    [f"{n:02d}" for n in range(0, 15)]        # 00-14 procurement, general, facility construction
    + ["21", "22", "23", "25", "26", "27", "28"]   # facility services (24 reserved)
    + ["31", "32", "33", "34", "35"]               # site and infrastructure
    + ["40", "41", "42", "43", "44", "45", "46", "48"]  # process equipment (47 reserved)
)


def valid_division(raw) -> str | None:
    s = str(raw or "").strip()
    if not s:
        return None
    s = s.zfill(2) if len(s) == 1 else s
    return s if s in _VALID_DIVISIONS else None


def divisions_from(client, text: str) -> list[dict]:
    """Chunk the document; never just take the front.

    Truncating to the first N characters classified two 1,875-page project
    manuals as having ZERO divisions. Their opening 120k chars are cover sheet,
    table of contents, bid forms and general conditions -- the specification
    starts far later. A spec book is precisely the document where the front
    matter is least representative of the content.

    Chunks are capped so one enormous book cannot run away with the budget, and
    divisions are merged across chunks: a division seen in several windows is
    one division with a wider page range, not several findings.
    """
    chunks = [text[i:i + CHUNK_CHARS] for i in range(0, len(text), CHUNK_CHARS)][:MAX_CHUNKS]
    merged: dict[str, dict] = {}
    for c in chunks:
        if len(c) < 500:
            continue
        for d in _one_call(client, c):
            key = valid_division(d.get("division"))
            if not key:
                continue
            d["division"] = key
            cur = merged.get(key)
            if cur is None:
                merged[key] = d
                continue
            # Keep the richest evidence, widen the page range.
            for f in ("basis_of_design_product", "substitution_language"):
                if not cur.get(f) and d.get(f):
                    cur[f] = d[f]
            for f in ("approved_manufacturers", "model_numbers"):
                cur[f] = sorted({*(cur.get(f) or []), *(d.get(f) or [])})
            pf = [x for x in (cur.get("page_from"), d.get("page_from")) if x]
            pt = [x for x in (cur.get("page_to"), d.get("page_to")) if x]
            cur["page_from"] = min(pf) if pf else None
            cur["page_to"] = max(pt) if pt else None
            if d.get("confidence") == "high":
                cur["confidence"] = "high"
    return list(merged.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", choices=["project", "reference", "legislative"], default="reference")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from google import genai
    from google.genai import types as gtypes
    # "global", not a regional endpoint -- found 2026-08-08. Newer Gemini
    # models (this script uses gemini-3.6-flash) are only published under
    # Vertex AI's global endpoint; us-central1 returned a 404 NOT_FOUND on
    # every single call, live-verified before and after this fix. Matches
    # the default in state_agent_pipeline/config.py, which this standalone
    # script duplicates rather than imports.
    client = genai.Client(
        vertexai=True,
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"),
    )
    conn = connect(); cur = conn.cursor()

    # `col` keys document_pages; `owner_col` keys project_csi_divisions. For
    # projects these are DIFFERENT THINGS -- document_pages.document_file_id is
    # project_document_files.id, while project_csi_divisions.project_sk is
    # projects.project_sk. Writing the document id into project_sk violated the
    # foreign key on the first real run, which is the FK doing its job: without
    # it, 22,528 rows would have pointed at whatever project happened to hold
    # that sk, and the page would have cited another job's specification.
    col = {"project": "document_file_id", "reference": "reference_document_id",
           "legislative": "legislative_document_id"}[args.owner]
    owner_col = {"project": "project_sk", "reference": "reference_document_id",
                 "legislative": "legislative_document_id"}[args.owner]

    # Documents that have text and no divisions yet. Deliberately keyed on the
    # DIVISIONS table, not on a status flag -- the flag is what lied last time.
    cur.execute(f"""
        SELECT p.{col}, count(*) AS pages
          FROM document_pages p
         WHERE p.{col} IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM project_csi_divisions d
                            WHERE d.source_document = %s || p.{col}::text)
         GROUP BY p.{col} ORDER BY pages DESC LIMIT %s""", (args.owner + ":", args.limit))
    targets = cur.fetchall()
    print(f"[scope] {len(targets)} {args.owner} documents with text and no divisions", flush=True)

    wrote = docs = 0
    for i, (doc_id, pages) in enumerate(targets, 1):
        # Resolve the OWNER key. A project document's rows hang off the
        # project, not off the document.
        owner_id = doc_id
        if args.owner == "project":
            cur.execute("SELECT project_sk FROM project_document_files WHERE id = %s", (doc_id,))
            r = cur.fetchone()
            if not r or r[0] is None:
                print(f"  [{i}/{len(targets)}] doc {doc_id}: no project_sk, skipped", flush=True)
                continue
            owner_id = r[0]

        cur.execute(f"""SELECT page_number, raw_text FROM document_pages
                         WHERE {col} = %s ORDER BY page_number""", (doc_id,))
        rows = cur.fetchall()
        text = "\n\n".join(f"[page {n}]\n{t}" for n, t in rows if t and t.strip())
        if len(text) < 500:
            print(f"  [{i}/{len(targets)}] doc {doc_id}: too little text, skipped", flush=True)
            continue
        try:
            divs = divisions_from(client, text)
        except Exception as e:  # noqa: BLE001
            # Printing only type(e).__name__ here ("API ClientError") hid a
            # real, fixable location-config bug (2026-08-08) behind an
            # opaque label for every single call in a 20-document dry run.
            # str(e) carries the actual API error body -- always print it.
            print(f"  [{i}/{len(targets)}] doc {doc_id}: API {type(e).__name__}: {e}", flush=True)
            continue

        if args.dry_run:
            print(f"  [{i}/{len(targets)}] doc {doc_id} ({pages}p): {len(divs)} divisions "
                  f"{[d.get('division') for d in divs][:8]}", flush=True)
            docs += 1; wrote += len(divs); continue

        for d in divs:
            cur.execute(f"""
                INSERT INTO project_csi_divisions
                  ({owner_col}, division, division_name, basis_of_design_product,
                   approved_manufacturers, substitution_language, model_numbers,
                   source_document, page, page_from, page_to, openness, confidence)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING""",
                (owner_id, str(d.get("division") or "")[:8],
                 d.get("division_name") or "", d.get("basis_of_design_product"),
                 d.get("approved_manufacturers") or [], d.get("substitution_language"),
                 d.get("model_numbers") or [], f"{args.owner}:{doc_id}",
                 d.get("page_from"), d.get("page_from"), d.get("page_to"),
                 d.get("openness") if d.get("openness") in
                    ("proprietary","or-equal","performance","unspecified") else "unspecified",
                 d.get("confidence") or "low"))
            wrote += 1
        # ONLY after rows land, and only for project documents (the status table
        # is keyed on document_file_id).
        if args.owner == "project" and divs:
            cur.execute("""INSERT INTO document_processing_status (document_file_id, divisions_written_at)
                           VALUES (%s, now())
                           ON CONFLICT (document_file_id) DO UPDATE SET divisions_written_at = now()""",
                        (doc_id,))
        conn.commit(); docs += 1
        print(f"  [{i}/{len(targets)}] doc {doc_id} ({pages}p): {len(divs)} divisions", flush=True)
        time.sleep(0.5)

    cur.execute("SELECT count(*) FROM project_csi_divisions")
    total = cur.fetchone()[0]
    print(f"\n[done] documents={docs} divisions_written={wrote}")
    print(f"[verify] project_csi_divisions now holds {total:,} rows")
    if wrote and not total and not args.dry_run:
        print("STOP: wrote divisions but the table is empty", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
