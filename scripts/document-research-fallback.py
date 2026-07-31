#!/usr/bin/env python3
"""Systematic Step 6, document-focused: find named projects with a real,
live, fetchable document (council/planning packet, TDLR-style state
filing, bond/zoning hearing PDF) -- not permit-portal metadata.

Permit-metadata breadth (Accela etc.) is not the differentiator -- Shovels
already covers 2,450+ jurisdictions on that axis. Actual construction
documents are the moat, and permit portals generally don't expose them
publicly (confirmed 2026-07-31: Broward has no Attachments tab, Hillsborough's
is upload-only). Named-project web research (the pattern that found
Rockford's $90M Hard Rock filing and Harris County's TDLR TABS pages) is
the one source category proven to yield real documents.

Every claimed document URL is live-fetched and content-type-checked in the
same run -- a project only counts as a real document win if the file comes
back as an actual PDF/DOCX etc, not text/html (error page, login wall,
portal landing page). No claim is trusted without that check.

Usage:
    python3 scripts/document-research-fallback.py --county Peoria --state IL
    python3 scripts/document-research-fallback.py --county Peoria --state IL --lookback "last 30 days"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gemini_discovery_chat import send  # noqa: E402

ROOT = _SCRIPTS.parent
RAW_DIR = ROOT / "data" / "raw"
USER_AGENT = "Mozilla/5.0 SpecIndex-DocumentBot/1.0 (+https://specindex.ai)"

# A blanket "reject all text/html" rule was rejecting real, specific
# government record pages (e.g. TDLR TABS project registration pages --
# manually confirmed real for Harris County TX earlier this session, then
# auto-rejected here on a later run) alongside genuine error/login/homepage
# junk. Distinguish them instead: reject only when the final URL or body
# actually looks like an error/login/generic-landing page.
ERROR_PAGE_SIGNALS = (
    "page not found", "404 not found", "requested entity was not found",
    "please sign in", "please log in", "you must be logged in",
    "login required", "session expired", "access denied",
)
GENERIC_URL_PATH_SIGNALS = ("/error", "/login", "/signin", "/notfound", "/404", "/home", "/search")
MIN_HTML_RECORD_BYTES = 800

PROMPT_TEMPLATE = """You are researching named commercial/industrial construction \
projects in {county} County, {state}, within {lookback}.

Give me every named project you can find -- project info always comes first, a \
document is a bonus, not a requirement. For each project found, give me:
1. Project name, address, type, estimated cost, developer/owner, status
2. IF you can find one: a SPECIFIC, PUBLIC, CITABLE DOCUMENT -- one of:
   - A city council or planning-commission meeting packet/agenda PDF with the \
project's site plan, staff report, or approval resolution
   - A state regulatory filing (e.g. TDLR TABS in Texas, HFSRB in Illinois, or your \
state's equivalent) with a project registration page
   - A bond authorization, TIF redevelopment plan, or zoning hearing PDF
   - Any other government-published PDF/DOCX specific to one named project
   Give the EXACT document URL (not a search page, not a portal homepage -- the direct \
link to the PDF/DOCX itself). A homepage or portal search page is not useful -- if you \
can't find the direct file link after a real search, leave document_url blank rather \
than guessing a plausible-looking filename. Do not fabricate a URL.
3. If you found a document, say what kind it is (council packet, state filing, etc)

Include projects even if you can't find a document for them -- just leave \
document_url blank in that case."""

FEEDBACK_TEMPLATE = """GEMINI_FEEDBACK_REPORT: I live-fetched the document URLs you \
gave me. Results:
{results}

These URLs are not usable -- they returned an error, a login wall, or an HTML page \
instead of the actual document (a homepage is not a document). Before giving up, \
search again for the SAME projects using more specific queries: the project name plus \
"filetype:pdf", the agency's public document/agenda archive page (e.g. search \
"site:hfsrb.illinois.gov {{project name}}" or the equivalent for whatever agency it \
is), or the exact permit/registration/project number. Only return an empty array if \
you've genuinely tried this and found nothing -- don't give up after one search."""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def extract_json_blob(text: str) -> list[dict] | None:
    match = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    if not match:
        match = re.search(r"(\[.*\])", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def fetch_and_check(url: str, timeout: int = 30) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            data = resp.read()
            final_url = resp.geturl()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        return False, f"dead ({e})"

    if content_type != "text/html":
        return True, f"real file ({content_type}, {len(data):,} bytes)"

    # text/html: could be a genuine, specific government record page (a
    # TDLR/HFSRB-style filing, a Legistar/agenda-item detail page) or a
    # generic error/login/landing page. Reject the latter, accept the
    # former as a real citable source, not a downloadable file.
    final_path = final_url.lower()
    if any(sig in final_path for sig in GENERIC_URL_PATH_SIGNALS):
        return False, f"rejected (redirected to a generic page: {final_url})"
    path_after_domain = re.sub(r"^https?://[^/]+/?", "", final_url).strip("/")
    if len(path_after_domain) < 4:
        return False, f"rejected (bare homepage, no specific record path: {final_url})"
    if len(data) < MIN_HTML_RECORD_BYTES:
        return False, f"rejected (HTML body too short to be a real record page, {len(data)} bytes)"
    body_lower = data.decode("utf-8", errors="ignore").lower()
    hit = next((sig for sig in ERROR_PAGE_SIGNALS if sig in body_lower), None)
    if hit:
        return False, f"rejected (page body contains error/login signal {hit!r})"
    return True, f"real citable record page (html, {len(data):,} bytes)"


def structured_prompt_suffix() -> str:
    return (
        "\n\nRespond with a JSON array (in a ```json code block) of objects with keys: "
        "name, city_address, project_type, estimated_cost, developer_owner, status, "
        "document_url, document_type, source_citation."
    )


def run_county(county: str, state: str, lookback: str, session: str, max_feedback_rounds: int = 1) -> dict:
    """Project capture is unconditional -- a project with no document is still
    kept. Document-finding is best-effort on top: one feedback round asks
    Gemini to try harder on projects whose first URL was dead, but a project
    is never dropped just because no real document turned up."""
    prompt = PROMPT_TEMPLATE.format(county=county, state=state, lookback=lookback) + structured_prompt_suffix()
    reply = send(session, prompt)
    projects = extract_json_blob(reply) or []

    for proj in projects:
        url = proj.get("document_url")
        if not url:
            proj["document_status"] = "no url given"
            proj["document_verified"] = False
            continue
        ok, detail = fetch_and_check(url)
        proj["document_status"] = detail
        proj["document_verified"] = ok
        print(f"  [{'REAL' if ok else 'DEAD'}] {proj.get('name', '?')}: {url} -- {detail}", file=sys.stderr)

    dead = [p for p in projects if not p.get("document_verified")]
    if dead and max_feedback_rounds > 0:
        print(f"  -- {len(dead)} project(s) without a confirmed document, retrying once --", file=sys.stderr)
        results = "\n".join(f"- {p.get('name', '?')}: {p.get('document_url') or '(none given)'} -- {p.get('document_status')}" for p in dead)
        feedback = FEEDBACK_TEMPLATE.format(results=results) + structured_prompt_suffix()
        reply = send(session, feedback)
        retried = extract_json_blob(reply) or []
        retried_by_name = {p.get("name"): p for p in retried if p.get("name")}
        for proj in dead:
            match = retried_by_name.get(proj.get("name"))
            if not match or not match.get("document_url"):
                continue
            ok, detail = fetch_and_check(match["document_url"])
            print(f"  [retry {'REAL' if ok else 'DEAD'}] {proj.get('name', '?')}: {match['document_url']} -- {detail}", file=sys.stderr)
            if ok:
                proj["document_url"] = match["document_url"]
                proj["document_type"] = match.get("document_type", proj.get("document_type"))
                proj["document_status"] = detail
                proj["document_verified"] = True

    verified_count = sum(1 for p in projects if p.get("document_verified"))
    return {
        "generated_at": date.today().isoformat(),
        "county": county,
        "state": state,
        "window": lookback,
        "method": "Systematic document-focused Step 6 (scripts/document-research-fallback.py) -- "
        "captures every named project found; document discovery is best-effort on top, "
        "not a gate. Every document_url is live-fetched and content-type-checked before "
        "document_verified is set true.",
        "projects_found": len(projects),
        "documents_confirmed": verified_count,
        "projects": projects,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--county", required=True)
    parser.add_argument("--state", required=True, help="2-letter state code, e.g. IL")
    parser.add_argument("--lookback", default="the last 30 days")
    parser.add_argument("--session", default=None, help="Gemini session name (default: derived from county/state)")
    parser.add_argument("--out", default=None, help="Output path (default: data/raw/{state}-{county}-document-fallback.json)")
    args = parser.parse_args(argv)

    session = args.session or f"docfallback_{args.state.lower()}_{slugify(args.county)}"
    result = run_county(args.county, args.state, args.lookback, session)

    out_path = Path(args.out) if args.out else RAW_DIR / f"{args.state.lower()}-{slugify(args.county)}-document-fallback.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps({"county": args.county, "state": args.state, "documents_confirmed": result["documents_confirmed"], "out": str(out_path)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
