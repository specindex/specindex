#!/usr/bin/env python3
"""Research live county-level permit/GIS data portals for a state's thin
or zero-coverage counties. State-agnostic version of the one-off GA
research pass -- reused as-is for Texas and every state after it.

Deterministic -> Flash -> Sonnet, matching the Agent-Per-State framework's
node order (see core/ingestion/ -- Node 1 is always the deterministic
step, LLM judgment is a fallback, not the default):
  0. Deterministic discovery -- ArcGIS Online's public search API
     (sharing/rest/search) and Socrata's discovery API
     (api.us.socrata.com/api/catalog/v1) are real, free, structured
     search APIs, not LLM guessing. Queried first for every county; any
     county with a confident hit here skips the Flash pass entirely --
     cheaper and less hallucination-prone than a search-grounded LLM.
  1. Gemini Flash + Google Search grounding -- only for counties the
     deterministic pass didn't resolve. High-recall gather of candidate
     portal URLs (over-include, don't filter yet).
  2. Claude Sonnet -- high-precision audit over the COMBINED deterministic
     + Flash candidate list: classify platform type (socrata/arcgis/ckan/
     other), consolidate near-duplicates, drop junk.
  3. HTTP verify (this script, not either model) -- neither model can
     guarantee a URL is actually live; only a real request can. Matches
     this project's standing discipline: verify every source live before
     building a puller against it.

This produces a research candidate list, NOT pull scripts -- each
promising, verified candidate still needs a real puller written and
manually confirmed against live data before merging, same as every other
source this session.

Usage:
  python3 scripts/research-county-sources.py --state Texas --state-code TX \
      --counties Harris,Dallas,Bexar,Travis,Collin,Denton
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw"

FLASH_BATCH = 6


def response_text(resp: Any) -> str:
    text = getattr(resp, "text", None)
    if text:
        return text
    parts = []
    for c in getattr(resp, "candidates", None) or []:
        content = getattr(c, "content", None)
        for p in getattr(content, "parts", None) or []:
            t = getattr(p, "text", None)
            if t:
                parts.append(t)
    return "\n".join(parts)


def extract_json_blob(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        import re

        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            raise
        return json.loads(m.group(1))


def _http_get_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "SpecIndex-Research/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def deterministic_arcgis_search(county: str, state_name: str) -> list[dict]:
    """ArcGIS Online's public search API -- real structured search over
    every publicly shared ArcGIS item (Feature Services, Map Services,
    Hub pages), not an LLM guess. No auth needed for public content."""
    import urllib.parse

    query = f'"{county} County" {state_name} permit type:"Feature Service"'
    url = "https://www.arcgis.com/sharing/rest/search?" + urllib.parse.urlencode(
        {"q": query, "f": "json", "num": 10, "sortField": "numViews", "sortOrder": "desc"}
    )
    try:
        data = _http_get_json(url)
    except Exception as e:  # noqa: BLE001
        print(f"[deterministic:arcgis] {county}: search failed: {e}", file=sys.stderr)
        return []

    out = []
    for item in data.get("results", []):
        item_url = item.get("url")
        if not item_url:
            continue
        out.append(
            {
                "county": county,
                "url": item_url,
                "platform_type": "arcgis",
                "title": item.get("title", ""),
                "confidence": 0.7,
                "flagged_uncertain": False,
                "notes": f"ArcGIS Online search hit, owner={item.get('owner', '?')}, views={item.get('numViews', '?')}",
                "source_pass": "deterministic",
            }
        )
    return out


def deterministic_socrata_search(county: str, state_name: str) -> list[dict]:
    """Socrata's own discovery API -- searches every Socrata-hosted open
    data portal nationwide by keyword. Real structured search, not a
    guess; no auth needed for public datasets."""
    import urllib.parse

    query = f"{county} County {state_name} building permits"
    url = "http://api.us.socrata.com/api/catalog/v1?" + urllib.parse.urlencode({"q": query, "limit": 5})
    try:
        data = _http_get_json(url)
    except Exception as e:  # noqa: BLE001
        print(f"[deterministic:socrata] {county}: search failed: {e}", file=sys.stderr)
        return []

    out = []
    for result in data.get("results", []):
        resource = result.get("resource", {})
        link = result.get("link") or result.get("permalink")
        if not link:
            continue
        out.append(
            {
                "county": county,
                "url": link,
                "platform_type": "socrata",
                "title": resource.get("name", ""),
                "confidence": 0.7,
                "flagged_uncertain": False,
                "notes": f"Socrata discovery API hit, domain={result.get('metadata', {}).get('domain', '?')}",
                "source_pass": "deterministic",
            }
        )
    return out


def _looks_relevant(county: str, candidate: dict) -> bool:
    """Both search APIs' q= param is a fuzzy keyword match, not a real
    geographic filter -- confirmed live: every GA county query returned
    the SAME Howard County MD / Marin County CA / LA City hits, and every
    TX county query returned the same generic data.texas.gov hits
    regardless of which county was asked for. A hit only counts as
    resolving a county if the county's own name actually appears in the
    URL or title -- anything else is noise that must fall through to
    Flash instead of silently being accepted as "found"."""
    key = county.lower().replace(" ", "").replace(".", "")
    haystack = (
        (candidate.get("url") or "") + " " + (candidate.get("title") or "") + " " + (candidate.get("notes") or "")
    ).lower().replace(" ", "")
    return key in haystack


def deterministic_discover(counties: list[str], state_name: str) -> tuple[list[dict], list[str]]:
    """Returns (candidates_found, counties_still_unresolved). A county is
    only "resolved" if at least one hit's county name literally appears
    in its URL/title -- see _looks_relevant()."""
    found: list[dict] = []
    unresolved: list[str] = []
    for county in counties:
        arcgis_hits = deterministic_arcgis_search(county, state_name)
        socrata_hits = deterministic_socrata_search(county, state_name)
        all_hits = arcgis_hits + socrata_hits
        relevant_hits = [h for h in all_hits if _looks_relevant(county, h)]
        print(
            f"[deterministic] {county}: {len(all_hits)} raw hit(s), {len(relevant_hits)} pass relevance filter",
            file=sys.stderr,
        )
        if relevant_hits:
            found.extend(relevant_hits)
        else:
            unresolved.append(county)
        time.sleep(0.3)
    return found, unresolved


def flash_gather(state_name: str, counties: list[str], model: str, project: str, location: str) -> dict:
    from google import genai
    from google.genai import types

    if model.startswith("gemini-2.5") and location == "global":
        location = "us-central1"

    client = genai.Client(vertexai=True, project=project, location=location)
    tools = [types.Tool(google_search=types.GoogleSearch())]
    all_candidates: list[dict] = []
    raw_chunks: list[str] = []
    batches = [counties[i : i + FLASH_BATCH] for i in range(0, len(counties), FLASH_BATCH)]

    for bi, batch in enumerate(batches, 1):
        county_list = "\n".join(f"- {c} County, {state_name}" for c in batch)
        prompt = f"""You are SpecIndex's high-recall data-source gatherer, working on our core
coverage-depth initiative: SpecIndex is only as valuable as the counties it
actually covers, and every county below currently has ZERO commercial
construction data in our corpus. Finding a real source for even one of
these counties is a direct, meaningful improvement to depth of coverage --
this is not a nice-to-have research exercise, it is the highest-priority
gap-closing work in the pipeline right now.

GOAL: For each county below, find the REAL, live public data source(s) a
developer could use to see current commercial building permits or
construction/development activity. Prefer over-inclusion -- if unsure,
include it and set flagged_uncertain=true.

PRIORITIZE BY BUILDABILITY, not just relevance -- a source we can actually
turn into a working automated puller closes a coverage gap; a source we
can only describe does not:
1. Socrata open-data portals (data.SUBDOMAIN.gov style, /resource/*.json
   API) -- highest priority, trivial to automate, same pattern already
   proven for NJ/Dallas/Collin.
2. ArcGIS REST FeatureServer/MapServer endpoints (.../rest/services/.../FeatureServer)
   -- second priority, same pattern already proven for NC/Mecklenburg.
3. CKAN open-data catalogs.
4. County GIS department "open data" or "data hub" pages that might link
   to one of the above.
5. Accela Citizen Access / Tyler EnerGov / iWorQ / SagesGov permit portals
   (aca-prod.accela.com or similar) -- lower priority (needs browser
   automation, not a simple API), but still real signal that the county
   has digitized permitting. Include these, just be honest in `notes`
   that this is a heavier scrape, not an API.
6. County planning/building department permit-search pages, even if not a
   clean API (note the URL anyway, flag as "manual/scrape" platform_type).

Return ONLY valid JSON (no markdown):
{{
  "candidates": [
    {{
      "county": "...",
      "url": "https://...",
      "platform_type": "socrata|arcgis|ckan|accela|manual_portal|other",
      "title": "...",
      "confidence": 0.0,
      "flagged_uncertain": false,
      "notes": "short reason, e.g. what you saw at this URL"
    }}
  ]
}}

Rules:
- Real public URLs only, found via search. No invented links -- a fabricated
  source actively hurts the coverage-depth goal by wasting the next
  verification pass on something that was never real.
- If a county genuinely appears to have no public permit data system, say so
  with a candidate entry with platform_type="none_found" and notes explaining.
- Today's date: {date.today().isoformat()}

COUNTIES:
{county_list}
"""
        print(f"[flash] batch {bi}/{len(batches)} ({len(batch)} counties)...", file=sys.stderr)
        text = ""
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=tools, temperature=0.2, response_mime_type="application/json"
                        ),
                    )
                except Exception:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt + "\n\nReturn ONLY the JSON object. No markdown fences.",
                        config=types.GenerateContentConfig(tools=tools, temperature=0.2),
                    )
                text = response_text(resp)
                if text.strip():
                    break
                raise RuntimeError("empty Flash response text")
            except Exception as e:
                last_err = e
                wait = 15 * (attempt + 1)
                print(f"[flash] retry {attempt + 1}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        else:
            # One bad batch must not discard every deterministic candidate
            # already found, or every other Flash batch's results -- log
            # and move on; this batch's counties just stay unresolved for
            # a future run instead of crashing the whole script.
            print(f"[flash] batch {bi} failed after retries ({last_err}) -- skipping, counties stay unresolved", file=sys.stderr)
            continue

        raw_chunks.append(f"=== batch {bi} ===\n{text}\n")
        try:
            blob = extract_json_blob(text)
            cands = blob.get("candidates") if isinstance(blob, dict) else blob
            if isinstance(cands, list):
                for c in cands:
                    if isinstance(c, dict) and c.get("url"):
                        c["source_pass"] = "flash"
                        all_candidates.append(c)
            else:
                print(f"[flash] batch {bi}: JSON had no candidates list", file=sys.stderr)
        except Exception as e:
            print(f"[flash] parse error batch {bi}: {e}; text_preview={text[:240]!r}", file=sys.stderr)
        time.sleep(2)

    return {
        "step": 1,
        "model": model,
        "generated_at": date.today().isoformat(),
        "county_count": len(counties),
        "candidate_count": len(all_candidates),
        "candidates": all_candidates,
        "raw_text": "\n".join(raw_chunks),
    }


def sonnet_audit(candidates: list[dict], model: str, api_key: str, max_retries: int = 3) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""You are SpecIndex's Model B: high-precision auditor and consolidator.

Gemini Flash (Model A) already gathered a high-recall candidate list of county
government data portals. Flash did NOT deduplicate or verify anything.

YOUR JOB:
- Group candidates that point to the SAME underlying system (e.g. a county GIS
  hub page vs. the actual ArcGIS REST endpoint it links to -- keep both if
  useful, but note the relationship)
- Classify platform_type as precisely as possible from the URL shape/notes
  (a URL containing /rest/services/.../FeatureServer is arcgis; a URL under
  a data.SUBDOMAIN.gov domain with /resource/ is socrata)
- Flag candidates that are clearly NOT a real data source (e.g. a generic
  county homepage with no permit-data path) as keep=false
- Set keep=true only for URLs worth a human/code HTTP-verification pass

Return ONLY valid JSON:
{{
  "candidates": [
    {{
      "county": "...",
      "url": "https://...",
      "platform_type": "socrata|arcgis|ckan|accela|manual_portal|other|none_found",
      "keep": true,
      "confidence": 0.0,
      "notes": "short reason"
    }}
  ],
  "dropped_count": 0
}}

Today's date: {date.today().isoformat()}

FLASH CANDIDATES (JSON):
{json.dumps(candidates, indent=2)[:150000]}
"""
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=8000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")
            if not text.strip():
                raise RuntimeError(f"empty Sonnet response (stop_reason={getattr(msg, 'stop_reason', '?')})")
            blob = extract_json_blob(text)
            return blob if isinstance(blob, dict) else {"candidates": blob, "dropped_count": 0}
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 5 * (attempt + 1)
            print(f"[sonnet] retry {attempt + 1}/{max_retries}: {e}; sleep {wait}s", file=sys.stderr)
            time.sleep(wait)
    print(f"[sonnet] failed after {max_retries} retries ({last_err}) -- falling back to un-audited candidates", file=sys.stderr)
    return {"candidates": candidates, "dropped_count": 0}


def http_verify(url: str, timeout: int = 15) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SpecIndex-Research/0.1"}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read(4096)
            looks_like_arcgis = b'"currentVersion"' in body or b"/rest/services" in url.encode()
            looks_like_socrata = b'"resource"' in body or b"/resource/" in url.encode()
            return {
                "http_status": status,
                "reachable": True,
                "looks_like_arcgis": looks_like_arcgis,
                "looks_like_socrata": looks_like_socrata,
            }
    except urllib.error.HTTPError as e:
        return {"http_status": e.code, "reachable": e.code < 500, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"http_status": None, "reachable": False, "error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True, help="Full state name, e.g. Texas")
    ap.add_argument("--state-code", required=True, help="Two-letter code, e.g. TX")
    ap.add_argument("--counties", required=True, help="Comma-separated county names")
    ap.add_argument("--flash-model", default="gemini-3.5-flash")
    ap.add_argument("--sonnet-model", default="claude-sonnet-5")
    ap.add_argument("--gcp-project", default="specindex-ai")
    ap.add_argument("--gcp-location", default="global")
    ap.add_argument("--skip-verify", action="store_true", help="Skip the HTTP verification pass")
    args = ap.parse_args()

    slug = args.state_code.lower()
    flash_raw = OUT_DIR / f"{slug}-county-sources-flash.json"
    sonnet_raw = OUT_DIR / f"{slug}-county-sources-sonnet.json"
    verified_path = OUT_DIR / f"{slug}-county-sources-verified.json"

    sys.path.insert(0, str(ROOT / "scripts"))
    from state_agent_pipeline.config import load_env

    load_env(ROOT)
    import os

    counties = [c.strip() for c in args.counties.split(",")]
    print(f"Researching {len(counties)} {args.state} counties: {', '.join(counties)}", file=sys.stderr)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    deterministic_candidates, unresolved = deterministic_discover(counties, args.state)
    print(
        f"[deterministic] {len(deterministic_candidates)} candidates across "
        f"{len(counties) - len(unresolved)}/{len(counties)} counties; "
        f"{len(unresolved)} counties still unresolved, going to Flash",
        file=sys.stderr,
    )

    if unresolved:
        flash_result = flash_gather(args.state, unresolved, args.flash_model, args.gcp_project, args.gcp_location)
        flash_raw.write_text(json.dumps(flash_result, indent=2) + "\n")
        print(f"[flash] {flash_result['candidate_count']} candidates -> {flash_raw}", file=sys.stderr)
        flash_candidates = flash_result["candidates"]
    else:
        flash_candidates = []
        print("[flash] skipped -- deterministic search resolved every county", file=sys.stderr)

    # Deterministic candidates came from real government-catalog search APIs
    # (ArcGIS Online, Socrata discovery) -- they're structured hits, not an
    # LLM guess, so they don't need Sonnet's precision-audit judgment. Only
    # Flash's search-grounded (higher hallucination-risk) candidates go to
    # Sonnet -- cuts LLM token spend to zero for any county the
    # deterministic pass alone resolves (e.g. all 16/16 for Texas).
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not flash_candidates:
        print("[sonnet] skipped -- no Flash candidates to audit (all counties resolved deterministically)", file=sys.stderr)
        audited = deterministic_candidates
    elif not api_key:
        print("ANTHROPIC_API_KEY not set -- skipping Sonnet audit, using pre-audit candidates as-is", file=sys.stderr)
        audited = deterministic_candidates + flash_candidates
    else:
        sonnet_result = sonnet_audit(flash_candidates, args.sonnet_model, api_key)
        sonnet_raw.write_text(json.dumps(sonnet_result, indent=2) + "\n")
        audited_flash = [c for c in sonnet_result.get("candidates", []) if c.get("keep", True)]
        print(f"[sonnet] {len(audited_flash)} kept, {sonnet_result.get('dropped_count', 0)} dropped -> {sonnet_raw}", file=sys.stderr)
        audited = deterministic_candidates + audited_flash

    if args.skip_verify:
        verified_path.write_text(json.dumps({"generated_at": date.today().isoformat(), "candidates": audited}, indent=2) + "\n")
        print(f"Skipped HTTP verify. Wrote {len(audited)} candidates -> {verified_path}")
        return 0

    verified = []
    for c in audited:
        url = c.get("url")
        if not url or c.get("platform_type") == "none_found":
            verified.append({**c, "verify": {"reachable": False, "skipped": True}})
            continue
        print(f"[verify] {c.get('county')}: {url}", file=sys.stderr)
        result = http_verify(url)
        verified.append({**c, "verify": result})
        time.sleep(0.5)

    verified_path.write_text(json.dumps({"generated_at": date.today().isoformat(), "candidates": verified}, indent=2) + "\n")

    reachable = [v for v in verified if v.get("verify", {}).get("reachable")]
    print(f"\n{len(reachable)}/{len(verified)} candidates reachable. Wrote -> {verified_path}")
    by_county: dict[str, list[dict]] = {}
    for v in reachable:
        by_county.setdefault(v.get("county", "?"), []).append(v)
    for county, cands in sorted(by_county.items()):
        print(f"\n{county}:")
        for c in cands:
            print(f"  [{c.get('platform_type')}] {c.get('url')} (status={c['verify'].get('http_status')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
