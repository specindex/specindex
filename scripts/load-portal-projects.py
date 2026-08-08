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
    # EVERY log, not the biggest one. The default used to be
    # max(..., key=size), so the broad all-states log from 2026-08-06 won every
    # time and a single-state capture could never load: a Maine run wrote 404
    # documents to a fresh log, the loader read the older file, and the corpus
    # moved by +0. Capture and load are separate steps, so the step that reads
    # must not silently pick a different file than the step that wrote.
    #
    # Reading all of them is safe: project creation and document linking are
    # both id-deduped, so a log processed twice adds nothing.
    if args.log:
        logs = [Path(args.log)]
    else:
        logs = sorted(logdir.glob("pull-*.csv"), key=lambda p: p.stat().st_mtime)
    # TWO scopes, deliberately different.
    #
    # `rows` (spec documents only) drives PROJECT CREATION and division
    # attachment -- a project earns a row because a real spec document proves it
    # exists, and divisions come from spec structure.
    #
    # `all_rows` (every successfully downloaded document) drives DOCUMENT
    # REGISTRATION. Filtering registration to CSI/DOT threw away 311 of 408
    # documents in the 2026-08-07 Maine log: every addendum, drawing, bid
    # tabulation and notice to contractors, because a one-page addendum has no
    # CSI structure and so carries no spec_format. That is the same mistake as
    # the `break` in the capture runner, one layer down -- a spec-shaped filter
    # discarding the documents that are not spec-shaped. The addenda are the
    # change record and the bid tabs name who won; neither is optional.
    rows, all_rows, seen, seen_all = [], [], set(), set()
    for lp in logs:
        for r in csv.DictReader(open(lp)):
            url = r.get("document_url") or r.get("url") or ""
            pid = r.get("project_id") or ""
            if r.get("status") == "downloaded" and url and (url, pid) not in seen_all:
                seen_all.add((url, pid))
                all_rows.append(r)
            if r.get("spec_format") not in ("CSI", "DOT SS/SP"):
                continue
            if (url, pid) in seen:
                continue
            seen.add((url, pid))
            rows.append(r)
    print(f"[scope] {len(logs)} pull log(s), newest {logs[-1].name if logs else '-'}: "
          f"{len(rows)} confirmed spec documents, "
          f"{len(all_rows)} documents of every kind", flush=True)

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
                -- NEVER downgrade a real name to a bare identifier. The pull log
                -- carries project_name = "3820" for portals that publish only a
                -- number, and cover-sheet enrichment had already replaced that
                -- with "MAINE STATE PRISON GATEHOUSE IMPROVEMENT PROJECT". A
                -- plain COALESCE(NULLIF(...,'')) treats "3820" as a perfectly
                -- good name and overwrote it -- re-running the loader silently
                -- undid the enrichment on every portal project.
                --
                -- Keep the incoming name only when it is not a bare identifier,
                -- or when what we hold is one.
                name = CASE
                    WHEN EXCLUDED.name ~ '^[0-9A-Za-z_.-]{1,14}$'
                         AND projects.name !~ '^[0-9A-Za-z_.-]{1,14}$'
                        THEN projects.name
                    ELSE COALESCE(NULLIF(EXCLUDED.name,''), projects.name)
                END,
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

    # REGISTER EVERY DOWNLOADED DOCUMENT against its project.
    #
    # This pass did not exist. The loop above only ever re-scoped a
    # reference_documents row that some earlier step had already inserted
    # (UPDATE ... WHERE url=), so a freshly captured document had nothing to
    # update and vanished between the pull log and the index: 404 documents
    # captured from Maine, 28 visible on projects.
    #
    # Documents land directly in project_document_files, which migration 057
    # established as the home for project-scoped material; reference_documents
    # stays for jurisdiction-wide standards.
    docs_registered = 0
    for r in all_rows:
        url = r.get("document_url") or r.get("url") or ""
        gcs = (r.get("gcs_path") or "").strip()
        # Compose the project_id the SAME WAY the creation loop above does. The
        # pull log carries the portal's own number ("3843"); the index key is
        # "me-portal-maine-vertical-3843". Looking up the raw number matched
        # nothing and registered 0 of 909 documents without erroring -- a clean
        # zero, which is this pipeline's standard failure signature.
        st = STATE_ABBR.get((r.get("state") or "").strip())
        num = (r.get("project_id") or "").strip()
        name = (r.get("project_name") or "").strip() or num
        if not (url and gcs and st and (num or name)):
            continue
        pid = f"{st.lower()}-portal-{slug(r.get('portal') or '')}-{slug(num or name)}"
        cur.execute("SELECT project_sk FROM projects WHERE project_id = %s", (pid,))
        got = cur.fetchone()
        if not got:
            continue
        # doc_type from the FILENAME -- the only field carrying the signal. The
        # title does not: the loader writes the project number into it.
        fn = (r.get("file_name") or url.rsplit("/", 1)[-1]).lower()
        # Prefer the type the capture runner stamped, which it decided from the
        # filename at the moment the filename was authoritative. The fallback
        # below only serves logs written before that column existed.
        doc_type = (r.get("doc_type") or "").strip() or (
                   "addendum" if "addend" in fn else
                    "drawing" if "drawing" in fn or "plan" in fn else
                    "bid_tab" if "tabulation" in fn or "bid_tab" in fn else
                    "advertisement" if "legal_ad" in fn or "advertis" in fn else
                    "notice" if "notice" in fn else
                   "specbook" if r.get("spec_format") in ("CSI", "DOT SS/SP") else
                   "other")
        cur.execute(
            """INSERT INTO project_document_files
                   (project_sk, title, url, content_type, gcs_path, doc_type,
                    spec_format, fetched_at, last_seen_at)
               VALUES (%s,%s,%s,'application/pdf',%s,%s,%s,now(),now())
               ON CONFLICT (project_sk, url) DO UPDATE SET
                   doc_type   = COALESCE(project_document_files.doc_type, EXCLUDED.doc_type),
                   last_seen_at = now()
               RETURNING (xmax = 0)""",
            (got[0], (r.get("file_name") or pid)[:500], url, gcs, doc_type,
             r.get("spec_format") or None),
        )
        ins = cur.fetchone()
        if ins and ins[0]:
            docs_registered += 1
    conn.commit()

    cur.execute("SELECT count(*) FROM projects"); after = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM project_csi_divisions WHERE project_sk IS NOT NULL")
    on_projects = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM project_document_files")
    docs_total = cur.fetchone()[0]
    print(f"[detail] documents registered this run={docs_registered}; "
          f"project_document_files holds {docs_total:,}")
    print(f"\n[after] corpus {after:,}  (+{after-before:,})")
    print(f"[detail] rows={created} divisions_attached={linked} skipped_multistate={skipped}")
    print(f"[verify] CSI divisions now ON A PROJECT: {on_projects}")
    if after < before:
        print("STOP: corpus decreased", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
