#!/usr/bin/env python3
"""Create projects FROM captured spec books, and attach their divisions.

WHY NOT A MATCHER. The obvious idea was to join spec books to existing permit
records by address. It cannot work: these documents describe STATE BID
SOLICITATIONS, and their identifiers are bid numbers -- "R2410-01", "3820",
"Brunswick HE-0016" -- not street addresses. The jobs are genuinely absent from
a permit corpus, because a state building project is procured before any local
permit exists.

So the spec book IS the project record. 224 of 229 confirmed spec documents
carry a project id and a name. Creating projects from them attaches 585 orphaned
CSI divisions -- currently sitting on documents where the record page cannot show
them -- to rows a user can actually open.

THE PROVENANCE IS BETTER THAN THE PERMIT CORPUS, not worse: every row here comes
with the document it was read from, that document's public URL, its fetch date
and its sha256. A permit row is a line in a feed; this is a project with its
specification attached.

ADDITIVE AND ID-DEDUPED. Corpus counts print before and after; a decrease exits
non-zero.
"""
from __future__ import annotations
import argparse, csv, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from specindex.db import connect  # noqa: E402

STATE_ABBR = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS",
    "Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD","Massachusetts":"MA",
    "Michigan":"MI","Minnesota":"MN","Mississippi":"MS","Missouri":"MO","Montana":"MT",
    "Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM",
    "New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
    "South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT",
    "Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY",
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logdir = ROOT / "coverage" / "pull-log"
    logpath = Path(args.log) if args.log else max(logdir.glob("pull-*.csv"),
                                                  key=lambda p: p.stat().st_size)
    rows = [r for r in csv.DictReader(open(logpath))
            if r.get("spec_format") in ("CSI", "DOT SS/SP")]
    print(f"[scope] {logpath.name}: {len(rows)} confirmed spec documents", flush=True)

    conn = connect(); cur = conn.cursor()
    cur.execute("SELECT count(*) FROM projects"); before = cur.fetchone()[0]
    print(f"[before] corpus {before:,}", flush=True)

    created = linked = skipped = 0
    for r in rows:
        state_name = (r.get("state") or "").strip()
        st = STATE_ABBR.get(state_name)
        if not st:                       # "multi" / "Utah, Washington" -- no single state
            skipped += 1
            continue
        num = (r.get("project_id") or "").strip()
        name = (r.get("project_name") or "").strip() or num
        if not (num or name):
            skipped += 1
            continue
        pid = f"{st.lower()}-portal-{slug(r.get('portal') or '')}-{slug(num or name)}"
        if args.dry_run:
            created += 1
            continue

        cur.execute(
            """
            INSERT INTO projects
                (project_id, name, state, status, opened_or_announced_date,
                 first_seen_at, last_updated_at)
            VALUES (%s, %s, %s, 'bidding', %s, now(), now())
            ON CONFLICT (project_id) DO UPDATE SET
                name = COALESCE(NULLIF(EXCLUDED.name,''), projects.name),
                last_updated_at = now()
            RETURNING project_sk
            """,
            (pid, name[:500], st, r.get("retrieved_date") or None),
        )
        sk = cur.fetchone()[0]
        created += 1

        # Attach the document, and move its divisions onto the project so the
        # record page can render them. This is the whole point: 585 divisions
        # existed and no page could show one.
        cur.execute("""UPDATE reference_documents SET scope='project', scope_value=%s
                        WHERE url=%s RETURNING id""", (pid, r.get("document_url")))
        got = cur.fetchone()
        if got:
            # Owner becomes the project; the document pointer MOVES to
            # source_document_id so the citation survives. Clearing it without
            # preserving it would leave an uncited manufacturer claim.
            cur.execute("""UPDATE project_csi_divisions
                              SET project_sk=%s,
                                  source_document_id=COALESCE(source_document_id, reference_document_id),
                                  reference_document_id=NULL
                            WHERE reference_document_id=%s AND project_sk IS NULL""",
                        (sk, got[0]))
            linked += cur.rowcount
        conn.commit()

    cur.execute("SELECT count(*) FROM projects"); after = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM project_csi_divisions WHERE project_sk IS NOT NULL")
    on_projects = cur.fetchone()[0]
    print(f"\n[after] corpus {after:,}  (+{after-before:,})")
    print(f"[detail] rows={created} divisions_attached={linked} skipped_multistate={skipped}")
    print(f"[verify] CSI divisions now ON A PROJECT: {on_projects}")
    if after < before:
        print("STOP: corpus decreased", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
