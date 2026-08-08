#!/usr/bin/env python3
"""Read project identity off the spec book cover sheet.

WHY. Maine 3820 rendered as a record titled "3820" with no location, no scope
and no architect -- while page 1 of the document we already held said:

    SPECIFICATIONS FOR
    MAINE STATE PRISON GATEHOUSE IMPROVEMENT PROJECT
    807 CUSHING ROAD. WARREN, MAINE
    PAUL DESIGNS PROJECT PLLC, PORTLAND ME
    BGS Project #3820

The portal lists the bid NUMBER because that is what a procurement system keys
on. The human name of the job is on the cover sheet, and we were parsing every
page of these books for CSI divisions while ignoring page 1.

A record called "3820" does not look like a project to a rep, however good the
specification panel beneath it is. This is the cheapest possible enrichment:
no new source, no new fetch, text already in Postgres.

GEMINI ON VERTEX, per the two-meter rule -- bulk mechanical extraction belongs on
GCP credits. Nothing is inferred: every field must appear literally on the page,
and a missing field stays null rather than being guessed. An invented address is
worse than none.
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

MODEL = "gemini-3.6-flash"

PROMPT = """This is the first page of a construction specification book.

Return STRICT JSON:
{"project_name": "...", "street_address": "...", "city": "...", "state": "ME",
 "architect": "...", "owner": "...", "bid_date": "2026-05-28", "scope": "..."}

RULES:
- Copy values LITERALLY from the page. Never infer, never expand abbreviations
  into guesses, never supply a value that is not printed.
- project_name: the human name of the job, NOT the bid number.
  "MAINE STATE PRISON GATEHOUSE IMPROVEMENT PROJECT" -- not "3820".
- architect: the design firm. It is usually the firm named under the project
  title with a city.
- owner: the agency or institution, if stated.
- scope: one short sentence describing the work, only if the page says.
- Any field not printed on the page: null. A null is correct; a guess is not.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from google import genai
    from google.genai import types
    client = genai.Client(vertexai=True, project=os.environ["GOOGLE_CLOUD_PROJECT"],
                          location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))
    conn = connect(); cur = conn.cursor()

    # Projects whose name is still just the bid number, and whose document we
    # have text for.
    # READS THE SPEC BOOK VIA project_document_files, not reference_documents.
    # Migration 057 moved page ownership for project-scoped spec books onto the
    # project's own document row, so the old join
    # (document_pages.reference_document_id = r.id) matched nothing and this
    # script reported "0 portal projects with document text" -- a clean zero,
    # from a scope query pointed at the pre-057 home.
    #
    # Scope is the spec book specifically: the cover sheet is page 1 of the
    # project manual, not of a bid tabulation.
    cur.execute("""
        SELECT p.project_sk, p.project_id, p.name, f.id
          FROM projects p
          JOIN project_document_files f ON f.project_sk = p.project_sk
                                       AND f.doc_type = 'specbook'
         WHERE p.project_id LIKE '%%-portal-%%'
           AND EXISTS (SELECT 1 FROM document_pages dp WHERE dp.document_file_id = f.id)
           -- Re-runnable: a project qualifies while its name is still a bare
           -- identifier, so a loader that clobbers a good name can be repaired
           -- by running this again. Keying on "has no city" made the repair
           -- impossible, because the city survived the clobbering.
           AND p.name ~ '^[0-9A-Za-z_.-]{1,14}$'
         LIMIT %s""", (args.limit or 100000,))
    targets = cur.fetchall()
    print(f"[scope] {len(targets)} portal projects with document text", flush=True)

    updated = 0
    for i, (sk, pid, name, rid) in enumerate(targets, 1):
        cur.execute("""SELECT raw_text FROM document_pages
                        WHERE document_file_id=%s ORDER BY page_number LIMIT 2""", (rid,))
        pages = [r[0] for r in cur.fetchall() if r[0]]
        text = "\n".join(pages)[:6000]
        if len(text) < 80:
            continue
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=PROMPT + "\n\n---\n\n" + text,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0))
            d = json.loads((resp.text or "{}").strip())
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}] {pid[:40]}: {type(e).__name__}", flush=True); continue

        nm = (d.get("project_name") or "").strip()
        # Reject a "name" that is just the bid number again.
        if nm and re.fullmatch(r"[A-Za-z]?[\d\-]{2,}", nm):
            nm = ""
        if args.dry_run:
            print(f"  [{i}] {name!r} -> {nm[:52]!r} | {d.get('city')} | {str(d.get('architect'))[:28]}",
                  flush=True)
            updated += 1
            continue

        cur.execute("""
            UPDATE projects SET
                name           = COALESCE(NULLIF(%s,''), name),
                street_address = COALESCE(NULLIF(%s,''), street_address),
                city           = COALESCE(NULLIF(%s,''), city),
                architect      = COALESCE(NULLIF(%s,''), architect),
                owner          = COALESCE(NULLIF(%s,''), owner),
                description    = COALESCE(NULLIF(%s,''), description),
                last_updated_at = now()
             WHERE project_sk=%s""",
            (nm[:500], (d.get("street_address") or "")[:200], (d.get("city") or "")[:100],
             (d.get("architect") or "")[:200], (d.get("owner") or "")[:200],
             (d.get("scope") or "")[:1000], sk))
        conn.commit(); updated += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(targets)}] updated={updated}", flush=True)
        time.sleep(0.3)

    cur.execute("""SELECT count(*) FROM projects
                    WHERE project_id LIKE '%%-portal-%%' AND city IS NOT NULL""")
    print(f"\n[done] updated={updated}")
    print(f"[verify] portal projects with a city: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
