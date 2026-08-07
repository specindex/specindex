#!/usr/bin/env python3
"""Fill the fields a portal project is missing, from what we already hold.

THE GAP. Side by side, a researched project and a portal project:

    Hyundai-SK Battery      description, $5B value, owner, project_type,
                            key_specs[], competitor_watch[]
    Maine 3820              name, city, architect -- and nothing else

The portal record looked thin next to it, so the page looked thin.

MOST OF THE GAP CLOSES WITH NO NEW DATA. competitor_watch is the biggest one and
it is free: the 16 CSI divisions already extracted from this project's spec book
ARE its trade list. Division 03 means concrete is in scope; 23 means HVAC. We
were holding the answer in another table and rendering an empty field.

project_type, description and key_specs come from the cover sheet and the
division mix, which are already in Postgres.

WHAT IS NOT INVENTED. estimated_value_usd stays null. A bid solicitation does
not state a construction value, and deriving one from square footage or division
count would be a plausible number in a field customers rank on -- the exact
failure the rules warn about. An absent value is honest; a fabricated one is
discovered the first time an estimator looks.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

# CSI division -> the trade a manufacturer rep would call it. Drives
# competitor_watch, which the record page's derived-scope panel reads.
DIVISION_TRADE = {
    "02": "demolition", "03": "concrete", "04": "masonry", "05": "structural steel",
    "06": "carpentry", "07": "roofing & waterproofing", "08": "doors & windows",
    "09": "finishes", "10": "specialties", "11": "equipment", "12": "furnishings",
    "13": "special construction", "14": "conveying", "21": "fire suppression",
    "22": "plumbing", "23": "hvac", "25": "building automation", "26": "electrical",
    "27": "communications", "28": "security & life safety", "31": "earthwork",
    "32": "site improvements", "33": "utilities",
}

PROMPT = """From this specification cover page, return STRICT JSON:
{"description":"one or two sentences describing the work","project_type":"one of: commercial|industrial|institutional|healthcare|education|infrastructure|residential|other","owner":"the agency or institution that owns the project, if stated","key_specs":["short factual bullets stated on the page"]}
Copy literally. Do not infer a value, a size, or a date that is not printed.
Any field not supported by the page: null, or [] for key_specs."""


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

    cur.execute("""
        SELECT p.project_sk, p.project_id, p.name, r.id
          FROM projects p
          JOIN reference_documents r ON r.scope_value = p.project_id AND r.scope='project'
         WHERE p.project_id LIKE '%%-portal-%%'
         LIMIT %s""", (args.limit,))
    targets = cur.fetchall()
    print(f"[scope] {len(targets)} portal projects", flush=True)

    done = 0
    for i, (sk, pid, name, rid) in enumerate(targets, 1):
        # FREE: the trade list is the divisions we already extracted.
        cur.execute("""SELECT DISTINCT division FROM project_csi_divisions
                        WHERE project_sk=%s ORDER BY division""", (sk,))
        divs = [d[0] for d in cur.fetchall()]
        trades = [DIVISION_TRADE[d] for d in divs if d in DIVISION_TRADE]

        cur.execute("""SELECT raw_text FROM document_pages
                        WHERE reference_document_id=%s ORDER BY page_number LIMIT 2""", (rid,))
        text = "\n".join(r[0] for r in cur.fetchall() if r[0])[:6000]

        d = {}
        if len(text) > 80:
            try:
                resp = client.models.generate_content(
                    model="gemini-3.6-flash", contents=PROMPT + "\n\n---\n\n" + text,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0))
                d = json.loads((resp.text or "{}").strip())
            except Exception:  # noqa: BLE001
                d = {}

        if args.dry_run:
            print(f"  [{i}] {str(name)[:34]:<36}trades={len(trades)} "
                  f"type={d.get('project_type')} specs={len(d.get('key_specs') or [])}", flush=True)
            done += 1
            continue

        cur.execute("""
            UPDATE projects SET
                description  = COALESCE(NULLIF(%s,''), description),
                project_type = COALESCE(NULLIF(%s,''), project_type),
                owner        = COALESCE(NULLIF(%s,''), owner),
                key_specs    = CASE WHEN jsonb_array_length(key_specs)=0
                                    THEN %s::jsonb ELSE key_specs END,
                competitor_watch = CASE WHEN jsonb_array_length(competitor_watch)=0
                                        THEN %s::jsonb ELSE competitor_watch END,
                last_updated_at = now()
             WHERE project_sk=%s""",
            ((d.get("description") or "")[:1000], (d.get("project_type") or "")[:40],
             (d.get("owner") or "")[:200],
             json.dumps([str(s)[:120] for s in (d.get("key_specs") or [])][:8]),
             json.dumps(trades), sk))
        conn.commit(); done += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(targets)}] enriched={done}", flush=True)
        time.sleep(0.25)

    cur.execute("""SELECT count(*) FROM projects
                    WHERE project_id LIKE '%%-portal-%%'
                      AND jsonb_array_length(competitor_watch) > 0""")
    print(f"\n[done] enriched={done}")
    print(f"[verify] portal projects with a trade list: {cur.fetchone()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
