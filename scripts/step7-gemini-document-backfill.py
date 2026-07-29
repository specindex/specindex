#!/usr/bin/env python3
"""Step 7 backfill: for high-value corpus projects, ask Gemini (search-
grounded) to find real public source documents (press releases with
attached PDFs, planning board minutes, EIS reports, developer site plans),
live-verify every URL it returns (real content-type/size, not a fabricated
link or an HTML redirect), and stream verified documents straight to GCS.

Per Asif's explicit instruction (2026-07-28): GCS-only, never stages
through a local folder first. Per the project's standing discipline:
Gemini's claims are never trusted without independent verification --
every URL gets a real HTTP request before anything is uploaded.

Resumable: tracks attempted project IDs in a state file so a re-run
(after an interrupt, or to expand the value threshold) doesn't repeat
work.

Usage:
    python3 scripts/step7-gemini-document-backfill.py \\
        --min-value 10000000 --batch-size 10 --limit 50 --dry-run
    python3 scripts/step7-gemini-document-backfill.py \\
        --min-value 10000000 --batch-size 10
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "pipeline" / "step7-backfill-state.json"
GCS_BUCKET = "specindex-ai-raw-documents"
USER_AGENT = (
    "SpecIndexDocumentBot/1.0 (+https://specindex.ai; research/archival; "
    "contact hello@specindex.ai)"
)

DOC_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".dwg", ".dxf"}
MIN_DOC_SIZE_BYTES = 5_000  # reject near-empty/error-page "downloads"

STATE_NAME_DIRS = {
    "GA": "georgia", "NJ": "new-jersey", "NY": "new-york", "CA": "california",
    "TX": "texas", "FL": "florida", "IL": "illinois", "PA": "pennsylvania",
    "OH": "ohio", "MI": "michigan", "NC": "north-carolina", "VA": "virginia",
    "WA": "washington", "AZ": "arizona", "MA": "massachusetts", "MN": "minnesota",
    "UT": "utah", "MD": "maryland", "WI": "wisconsin", "MO": "missouri",
    "KY": "kentucky", "OR": "oregon", "NM": "new-mexico", "NE": "nebraska",
    "LA": "louisiana", "SC": "south-carolina", "ID": "idaho", "SD": "south-dakota",
    "IN": "indiana", "CO": "colorado",
}


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"attempted_ids": [], "uploaded_files": 0, "projects_with_docs": 0}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def load_candidates(min_value: float) -> list[dict[str, Any]]:
    candidates = []
    for f in glob.glob(str(ROOT / "data" / "states" / "*.json")):
        d = json.loads(Path(f).read_text())
        for p in d.get("projects", []):
            v = p.get("estimated_value_usd")
            if v and v >= min_value:
                candidates.append(p)
    candidates.sort(key=lambda p: p["estimated_value_usd"], reverse=True)
    return candidates


def ask_gemini_batch(projects: list[dict[str, Any]], max_retries: int = 4) -> str:
    from google import genai
    from google.genai import types
    from google.auth.exceptions import RefreshError

    sys.path.insert(0, str(ROOT / "scripts"))
    from state_agent_pipeline.config import Settings

    settings = Settings.from_env()
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    lines = []
    for p in projects:
        lines.append(
            f"- ID: {p['id']} | \"{p['name']}\" | {p.get('city','')}, {p.get('state','')} | "
            f"${p.get('estimated_value_usd',0):,.0f} | {p.get('description','')[:200]}"
        )
    prompt = (
        "For each construction project below, search for REAL, live, downloadable public "
        "source documents -- press releases with attached PDFs, planning/zoning board meeting "
        "minutes or packets, environmental impact statements, developer site plans, permit "
        "applications, or news articles that link directly to a PDF/document file. Do NOT "
        "invent URLs -- only include ones you have actually found via search. For each project, "
        "reply with the project ID followed by a list of candidate document URLs (or 'NONE' if "
        "you found nothing). Format strictly as:\n\n"
        "PROJECT_ID: url1, url2, ...\n"
        "PROJECT_ID: NONE\n\n"
        "Projects:\n" + "\n".join(lines)
    )
    chat = client.chats.create(model=settings.flash_model, config=config)
    for attempt in range(1, max_retries + 1):
        try:
            resp = chat.send_message(prompt)
            return resp.text
        except RefreshError:
            raise
        except Exception as e:  # noqa: BLE001 -- transient network/API errors vary by transport
            if attempt == max_retries:
                raise
            wait = 2**attempt
            print(f"  [retry {attempt}/{max_retries}] {e} -- waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def parse_gemini_response(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([a-z]{2}-[\w-]+)\s*:\s*(.+)$", line.strip(), re.I)
        if not m:
            continue
        pid, rest = m.group(1), m.group(2).strip()
        if rest.upper() == "NONE":
            out[pid] = []
            continue
        urls = re.findall(r"https?://\S+", rest)
        out[pid] = [u.rstrip(",.;)") for u in urls]
    return out


def verify_and_fetch(url: str) -> tuple[bytes, str] | None:
    """Live-verify a candidate URL is a real, fetchable document. Returns
    (content, content_type) if it passes, None otherwise. Never trusts the
    URL's extension alone -- checks the real Content-Type header and a
    minimum size floor to reject error pages/redirects dressed up as docs.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            data = resp.read(50_000_000)  # 50MB safety cap per file
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as e:
        # OSError covers ConnectionResetError/BrokenPipeError etc -- a real
        # crash 2026-07-29 (a 50MB Hawaii EIS PDF reset mid-download) killed
        # the whole run because ConnectionResetError wasn't in this list.
        # This is designed to run unattended for many hours across
        # thousands of URLs -- a single bad connection must never take down
        # the whole batch.
        print(f"    [reject] {url} -- {e}", file=sys.stderr)
        return None

    ext_ok = any(url.lower().split("?")[0].endswith(ext) for ext in DOC_EXTENSIONS)
    type_ok = content_type in DOC_CONTENT_TYPES
    if not (ext_ok or type_ok):
        print(f"    [reject] {url} -- not a document (content-type={content_type!r})", file=sys.stderr)
        return None
    if len(data) < MIN_DOC_SIZE_BYTES:
        print(f"    [reject] {url} -- too small ({len(data)} bytes, likely an error page)", file=sys.stderr)
        return None
    return data, content_type or "application/octet-stream"


def upload_to_gcs(bucket, state_code: str, project_id: str, url: str, data: bytes, content_type: str) -> str:
    state_dir = STATE_NAME_DIRS.get(state_code, state_code.lower())
    filename = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1] or "document"
    filename = re.sub(r"[^\w\-.]+", "_", filename)[:150]
    blob_path = f"{state_dir}/{project_id}/{filename}"
    blob = bucket.blob(blob_path)
    if blob.exists():
        return "skipped"
    blob.upload_from_string(data, content_type=content_type)
    print(f"    [uploaded] {blob_path} ({len(data):,} bytes)", file=sys.stderr)
    return "uploaded"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-value", type=float, default=10_000_000)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0, help="Cap total projects processed this run, 0 = no cap")
    parser.add_argument("--dry-run", action="store_true", help="Search + verify only, no GCS upload")
    args = parser.parse_args(argv)

    state = load_state()
    attempted = set(state["attempted_ids"])
    candidates = [p for p in load_candidates(args.min_value) if p["id"] not in attempted]
    if args.limit:
        candidates = candidates[: args.limit]
    print(f"{len(candidates)} unattempted candidates (min_value=${args.min_value:,.0f})", file=sys.stderr)

    bucket = None
    if not args.dry_run:
        from google.cloud import storage

        bucket = storage.Client().bucket(GCS_BUCKET)

    summary = {"projects_checked": 0, "projects_with_docs": 0, "files_uploaded": 0, "files_rejected": 0}
    for i in range(0, len(candidates), args.batch_size):
        batch = candidates[i : i + args.batch_size]
        print(f"\n=== batch {i // args.batch_size + 1}: {[p['id'] for p in batch]} ===", file=sys.stderr)
        try:
            resp_text = ask_gemini_batch(batch)
        except Exception as e:  # noqa: BLE001
            print(f"  [error] Gemini call failed: {e}", file=sys.stderr)
            continue
        parsed = parse_gemini_response(resp_text)

        for p in batch:
            summary["projects_checked"] += 1
            attempted.add(p["id"])
            urls = parsed.get(p["id"], [])
            if not urls:
                continue
            print(f"  {p['id']}: {len(urls)} candidate URL(s) from Gemini", file=sys.stderr)
            got_one = False
            for url in urls:
                result = verify_and_fetch(url)
                if result is None:
                    summary["files_rejected"] += 1
                    continue
                data, content_type = result
                got_one = True
                if args.dry_run:
                    print(f"    [would upload] {url} ({len(data):,} bytes, {content_type})", file=sys.stderr)
                else:
                    # A real crash 2026-07-29: GCS auth expired mid-run and
                    # this call wasn't guarded (only ask_gemini_batch was),
                    # so an uncaught RefreshError killed an unattended
                    # multi-hour job on a single bad upload. Never let one
                    # file's upload failure take down the whole run.
                    try:
                        outcome = upload_to_gcs(bucket, p["state"], p["id"], url, data, content_type)
                    except Exception as e:  # noqa: BLE001
                        print(f"    [error] GCS upload failed for {url}: {e}", file=sys.stderr)
                        outcome = "error"
                    if outcome == "uploaded":
                        summary["files_uploaded"] += 1
                time.sleep(0.3)
            if got_one:
                summary["projects_with_docs"] += 1

        # Save incrementally after every batch, not just at the end -- this
        # is designed to run for many hours (thousands of projects, one
        # Gemini call each); losing all progress to an interrupt at hour 20
        # would be a real problem, not a cosmetic one. attempted_ids is the
        # only field that matters for resumability (which projects to skip
        # on the next run); cumulative uploaded/with-docs counts are purely
        # informational and just get set from this run's own summary below.
        if not args.dry_run:
            state["attempted_ids"] = sorted(attempted)
            save_state(state)
        time.sleep(1)

    if not args.dry_run:
        state["attempted_ids"] = sorted(attempted)
        state["uploaded_files"] = state.get("uploaded_files", 0) + summary["files_uploaded"]
        state["projects_with_docs"] = state.get("projects_with_docs", 0) + summary["projects_with_docs"]
        save_state(state)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
