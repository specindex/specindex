#!/usr/bin/env python3
"""NJ dual-model document pipeline.

Order (fixed):
  0. Socrata NJ DCA  — deterministic commercial permit corpus
  1. Gemini Flash    — Model A high-recall gather (Vertex); over-include, no dedupe
  2. Claude Sonnet   — Model B high-precision dedupe/consolidation/golden records
                       (Anthropic direct default; Vertex when quota works)
  3. Exact URL hash  — code safety net only after Sonnet (not instead of Sonnet)
  4. HTTP verify     — durable file URLs only
  5. Download + public page JSON

Usage:
  python3 scripts/test-nj-flash-sonnet-pipeline.py --download
  python3 scripts/test-nj-flash-sonnet-pipeline.py --limit 8 --download
  python3 scripts/test-nj-flash-sonnet-pipeline.py --skip-llm --download
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

OUT_DIR = ROOT / "data" / "raw"
PUBLIC_DIR = ROOT / "public" / "data"
CURATED_INPUT = ROOT / "data" / "raw" / "nj-2026-docs-input.json"
SOCRATA_SNAP = OUT_DIR / "nj-flash-sonnet-pipeline-socrata.json"
FLASH_RAW = OUT_DIR / "nj-flash-sonnet-pipeline-flash.json"
SONNET_RAW = OUT_DIR / "nj-flash-sonnet-pipeline-sonnet.json"
VERIFIED = OUT_DIR / "nj-flash-sonnet-pipeline-verified.json"
DOWNLOAD_LIST = OUT_DIR / "nj-flash-sonnet-pipeline-to-download.json"
PUBLIC_JSON = PUBLIC_DIR / "nj-flash-sonnet-pipeline.json"
PAGE_SUMMARY = OUT_DIR / "nj-flash-sonnet-pipeline.json"

DOC_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".dwg", ".dxf", ".rvt", ".ifc",
}
USER_AGENT = (
    "SpecIndexDocumentBot/1.0 (+https://specindex.ai; research/archival; "
    "contact hello@specindex.ai)"
)
ctx = ssl.create_default_context()
FLASH_BATCH = 8
SONNET_BATCH = 12


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def extract_json_blob(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if not m:
        raise ValueError("no JSON object/array found in model output")
    return json.loads(m.group(1))


def response_text(resp: Any) -> str:
    """Pull text from a Vertex generate_content response, including multi-part replies."""
    text = getattr(resp, "text", None) or ""
    if text.strip():
        return text
    parts: list[str] = []
    for c in getattr(resp, "candidates", None) or []:
        content = getattr(c, "content", None)
        for p in getattr(content, "parts", None) or []:
            t = getattr(p, "text", None)
            if t:
                parts.append(t)
    return "\n".join(parts)


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parts = urllib.parse.urlsplit(url)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = re.sub(r"/+", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    q = urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
    q = [(k, v) for k, v in q if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    query = urllib.parse.urlencode(sorted(q))
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]


def project_lines(projects: list[dict]) -> str:
    lines = []
    for p in projects:
        known = []
        for s in p.get("existing_sources") or p.get("sources") or []:
            u = s.get("url") or ""
            if u:
                known.append(u)
        lines.append(
            f"{p.get('id')} | {p.get('name')} | {p.get('city') or ''} | "
            f"{p.get('owner') or ''} | known:{'; '.join(known)}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 0 — Socrata NJ DCA
# ---------------------------------------------------------------------------

def pull_socrata(months: int = 6, page_cap: int = 500) -> dict:
    """Deterministic first pass: commercial permits from data.nj.gov/w9se-dmra."""
    spec = importlib.util.spec_from_file_location("pull_nj_dca", ROOT / "scripts" / "pull-nj-dca.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cutoff = date.today() - timedelta(days=int(months * 30.44))
    print(f"[socrata] pulling NJ DCA commercial permits since {cutoff}…", file=sys.stderr)
    projects = mod.pull(cutoff)
    # Rank by value for enrichment / page browse; keep a capped public list
    def value(p: dict) -> float:
        try:
            return float(p.get("estimated_value_usd") or 0)
        except (TypeError, ValueError):
            return 0.0

    ranked = sorted(projects, key=value, reverse=True)
    page_projects = ranked[:page_cap]
    snap = {
        "step": 0,
        "source": "socrata",
        "domain": "data.nj.gov",
        "dataset": "w9se-dmra",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "months": months,
        "cutoff": cutoff.isoformat(),
        "total_commercial": len(projects),
        "page_cap": page_cap,
        "projects": page_projects,
    }
    SOCRATA_SNAP.write_text(json.dumps(snap, indent=2) + "\n")
    print(f"[socrata] {len(projects)} commercial; page list {len(page_projects)}", file=sys.stderr)
    return snap


def load_enrichment_projects(limit: int = 0, include_socrata_top: int = 0) -> list[dict]:
    """Curated NJ 2026 list (known URLs) plus optional top Socrata by value."""
    projects: list[dict] = []
    seen: set[str] = set()
    if CURATED_INPUT.exists():
        data = json.loads(CURATED_INPUT.read_text())
        for p in data.get("projects") or []:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            projects.append(
                {
                    "id": pid,
                    "name": p.get("name") or "",
                    "city": p.get("city") or "",
                    "county": p.get("county") or "",
                    "owner": p.get("owner") or "",
                    "project_type": p.get("project_type") or "",
                    "opened_or_announced_date": p.get("opened_or_announced_date") or "",
                    "existing_sources": p.get("existing_sources") or [],
                    "origin": "curated",
                }
            )
    if include_socrata_top > 0 and SOCRATA_SNAP.exists():
        snap = json.loads(SOCRATA_SNAP.read_text())
        for p in (snap.get("projects") or [])[:include_socrata_top]:
            pid = p.get("id")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            projects.append(
                {
                    "id": pid,
                    "name": p.get("name") or "",
                    "city": p.get("city") or "",
                    "county": p.get("county") or "",
                    "owner": p.get("owner") or "",
                    "project_type": p.get("project_type") or "",
                    "opened_or_announced_date": p.get("opened_or_announced_date") or "",
                    "existing_sources": p.get("sources") or [],
                    "origin": "socrata",
                }
            )
    if limit and limit > 0:
        projects = projects[:limit]
    return projects


# ---------------------------------------------------------------------------
# Step 1 — Gemini Flash gather
# ---------------------------------------------------------------------------

def flash_gather(projects: list[dict], model: str, project: str, location: str) -> dict:
    from google import genai
    from google.genai import types

    # gemini-2.5-flash is regional; 3.x flash wants global.
    if model.startswith("gemini-2.5") and location == "global":
        location = "us-central1"
        print(f"[flash] using location={location} for {model}", file=sys.stderr)

    client = genai.Client(vertexai=True, project=project, location=location)
    tools = [types.Tool(google_search=types.GoogleSearch())]
    all_docs: list[dict] = []
    raw_chunks: list[str] = []
    batches = [projects[i : i + FLASH_BATCH] for i in range(0, len(projects), FLASH_BATCH)]

    for bi, batch in enumerate(batches, 1):
        prompt = f"""You are SpecIndex's high-recall document gatherer for New Jersey construction projects.

GOAL: Catch every possible PUBLIC construction document URL. Prefer over-inclusion.
If unsure whether a URL is relevant or distinct, INCLUDE it and set "flagged_uncertain": true.

For EACH project below, search the public web for:
- specification books / project manuals / CSI MasterFormat PDFs
- drawings / blueprints / plan sets
- bid packages / RFPs / advertisements
- environmental impact statements / EIS
- planning board / zoning / site plan PDFs
- board books / agendas with project attachments
- press releases that link to durable files

Return ONLY valid JSON (no markdown):
{{
  "documents": [
    {{
      "project_id": "nj-...",
      "project_name": "...",
      "title": "...",
      "url": "https://...",
      "doc_type": "spec_book|drawings|bid_package|eis|agenda_attachment|board_book|press_release|other",
      "confidence": 0.0,
      "flagged_uncertain": false,
      "notes": "short reason"
    }}
  ]
}}

Rules:
- Real public URLs only. No invented links.
- Prefer direct .pdf/.zip/.docx file URLs when they exist.
- Today's date: {date.today().isoformat()}

PROJECTS:
{project_lines(batch)}
"""
        print(f"[flash] batch {bi}/{len(batches)} ({len(batch)} projects)…", file=sys.stderr)
        last_err: Exception | None = None
        text = ""
        for attempt in range(4):
            try:
                # Prefer JSON mime when possible; Google Search tool often rejects it,
                # so fall back to plain generation with the same prompt.
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=tools,
                            temperature=0.2,
                            response_mime_type="application/json",
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
            raise SystemExit(f"Flash failed after retries: {last_err}")

        raw_chunks.append(f"=== batch {bi} ===\n{text}\n")
        try:
            blob = extract_json_blob(text)
            docs = blob.get("documents") if isinstance(blob, dict) else blob
            if isinstance(docs, list):
                for d in docs:
                    if isinstance(d, dict) and d.get("url"):
                        d["source_pass"] = "flash"
                        all_docs.append(d)
            else:
                print(f"[flash] batch {bi}: JSON had no documents list", file=sys.stderr)
        except Exception as e:
            print(f"[flash] parse error batch {bi}: {e}; text_preview={text[:240]!r}", file=sys.stderr)
        time.sleep(2)

    return {
        "step": 1,
        "model": model,
        "pass": "gather_high_recall",
        "backend": "vertex",
        "generated_at": date.today().isoformat(),
        "project_count": len(projects),
        "document_count": len(all_docs),
        "documents": all_docs,
        "raw_text": "\n".join(raw_chunks),
    }


def code_dedupe(docs: list[dict]) -> list[dict]:
    by_hash: dict[str, dict] = {}
    for d in docs:
        url = (d.get("url") or "").strip()
        if not url:
            continue
        key = url_hash(url)
        if key not in by_hash:
            nd = dict(d)
            nd["normalized_url"] = normalize_url(url)
            nd["url_hash"] = key
            by_hash[key] = nd
        else:
            prev = by_hash[key]
            if float(d.get("confidence") or 0) > float(prev.get("confidence") or 0):
                for k in ("title", "doc_type", "notes", "project_id", "project_name", "confidence"):
                    if d.get(k):
                        prev[k] = d[k]
            if d.get("flagged_uncertain") is False:
                prev["flagged_uncertain"] = False
    return list(by_hash.values())


# ---------------------------------------------------------------------------
# Step 3 — Sonnet audit (Anthropic direct default; Vertex optional)
# ---------------------------------------------------------------------------

def _sonnet_prompt(batch: list[dict], payload: list[dict]) -> str:
    return f"""You are SpecIndex's Model B: high-precision consolidator and deduplicator.

Gemini Flash (Model A) already gathered a high-recall candidate list. Flash did NOT
deduplicate. You see the full candidate set for these projects and must produce the
golden record list.

INPUTS:
1) Project list (ground truth IDs)
2) Complete Flash candidate list (may include near-duplicates, mirror URLs, junk)

YOUR JOB (you own deduplication):
- Group candidates that refer to the SAME document into one golden record
  (e.g. same PDF via http vs https, tracking params, CDN mirror, or retitled copy)
- Choose the best URL, title, doc_type, and project_id for each group
- Drop dead/irrelevant/junk URLs
- Prefer durable file URLs (.pdf/.zip/.docx) over HTML listing pages when both exist
- If a CRITICAL public document is clearly missing for NJSDA school projects or
  NJEDA awards, search and ADD a real public URL
- Set keep=true only for documents worth downloading
- Set action=merged when you collapsed duplicates into one row

Return ONLY valid JSON:
{{
  "documents": [
    {{
      "project_id": "nj-...",
      "project_name": "...",
      "title": "...",
      "url": "https://...",
      "doc_type": "spec_book|drawings|bid_package|eis|agenda_attachment|board_book|press_release|other",
      "confidence": 0.0,
      "keep": true,
      "action": "kept|merged|added|dropped",
      "merged_from_count": 1,
      "notes": "short reason"
    }}
  ],
  "dropped_count": 0,
  "added_count": 0,
  "merged_groups": 0
}}

Rules:
- Real public URLs only. No invented links.
- Do not invent CSI manuals that are behind login portals; if only a portal exists, omit it.
- Today's date: {date.today().isoformat()}

PROJECTS:
{project_lines(batch)}

FLASH CANDIDATES (JSON) — full list, not pre-deduped:
{json.dumps(payload, indent=2)[:120000]}
"""


def sonnet_via_anthropic(projects: list[dict], flash_docs: list[dict], model: str) -> dict:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    all_docs: list[dict] = []
    raw_chunks: list[str] = []
    batches = [projects[i : i + SONNET_BATCH] for i in range(0, len(projects), SONNET_BATCH)]

    for bi, batch in enumerate(batches, 1):
        ids = {p["id"] for p in batch}
        subset = [d for d in flash_docs if d.get("project_id") in ids]
        orphan = [d for d in flash_docs if not d.get("project_id")]
        payload = subset + orphan
        prompt = _sonnet_prompt(batch, payload)
        print(
            f"[sonnet/anthropic] batch {bi}/{len(batches)} "
            f"({len(batch)} projects, {len(payload)} candidates)…",
            file=sys.stderr,
        )
        last_err: Exception | None = None
        text = ""
        for attempt in range(3):
            try:
                msg = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=[{"role": "user", "content": prompt}],
                )
                parts = []
                for block in msg.content:
                    if getattr(block, "type", None) == "text":
                        parts.append(block.text)
                text = "\n".join(parts)
                break
            except Exception as e:
                last_err = e
                wait = 20 * (attempt + 1)
                print(f"[sonnet] retry {attempt + 1}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        else:
            raise SystemExit(f"Sonnet failed after retries: {last_err}")

        raw_chunks.append(f"=== batch {bi} ===\n{text}\n")
        try:
            blob = extract_json_blob(text)
            docs = blob.get("documents") if isinstance(blob, dict) else blob
            if isinstance(docs, list):
                for d in docs:
                    if isinstance(d, dict) and d.get("url"):
                        d["source_pass"] = "sonnet"
                        all_docs.append(d)
        except Exception as e:
            print(f"[sonnet] parse error batch {bi}: {e}", file=sys.stderr)
        time.sleep(2)

    kept = [d for d in all_docs if d.get("keep", True) and d.get("action") != "dropped"]
    return {
        "step": 3,
        "model": model,
        "pass": "audit_high_precision",
        "backend": "anthropic",
        "generated_at": date.today().isoformat(),
        "project_count": len(projects),
        "document_count_raw": len(all_docs),
        "document_count_kept": len(kept),
        "documents": kept,
        "documents_all": all_docs,
        "raw_text": "\n".join(raw_chunks),
    }


def sonnet_via_vertex(projects: list[dict], flash_docs: list[dict], model: str, location: str) -> dict:
    """Vertex Claude path. Requires quota on anthropic-claude-sonnet (currently 0 on new projects)."""
    from anthropic import AnthropicVertex

    gcp = os.environ.get("GOOGLE_CLOUD_PROJECT", "specindex-ai")
    client = AnthropicVertex(project_id=gcp, region=location)
    all_docs: list[dict] = []
    raw_chunks: list[str] = []
    batches = [projects[i : i + SONNET_BATCH] for i in range(0, len(projects), SONNET_BATCH)]

    for bi, batch in enumerate(batches, 1):
        ids = {p["id"] for p in batch}
        subset = [d for d in flash_docs if d.get("project_id") in ids]
        orphan = [d for d in flash_docs if not d.get("project_id")]
        payload = subset + orphan
        prompt = _sonnet_prompt(batch, payload)
        print(
            f"[sonnet/vertex] batch {bi}/{len(batches)} "
            f"({len(batch)} projects, {len(payload)} candidates)…",
            file=sys.stderr,
        )
        last_err: Exception | None = None
        text = ""
        for attempt in range(3):
            try:
                # Vertex Claude does not expose Anthropic web_search tool the same way.
                msg = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = "".join(getattr(b, "text", "") for b in msg.content)
                break
            except Exception as e:
                last_err = e
                wait = 20 * (attempt + 1)
                print(f"[sonnet/vertex] retry {attempt + 1}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        else:
            raise SystemExit(f"Vertex Sonnet failed after retries: {last_err}")

        raw_chunks.append(f"=== batch {bi} ===\n{text}\n")
        try:
            blob = extract_json_blob(text)
            docs = blob.get("documents") if isinstance(blob, dict) else blob
            if isinstance(docs, list):
                for d in docs:
                    if isinstance(d, dict) and d.get("url"):
                        d["source_pass"] = "sonnet"
                        all_docs.append(d)
        except Exception as e:
            print(f"[sonnet/vertex] parse error batch {bi}: {e}", file=sys.stderr)
        time.sleep(2)

    kept = [d for d in all_docs if d.get("keep", True) and d.get("action") != "dropped"]
    return {
        "step": 3,
        "model": model,
        "pass": "audit_high_precision",
        "backend": "vertex",
        "generated_at": date.today().isoformat(),
        "project_count": len(projects),
        "document_count_raw": len(all_docs),
        "document_count_kept": len(kept),
        "documents": kept,
        "documents_all": all_docs,
        "raw_text": "\n".join(raw_chunks),
    }


def sonnet_audit(projects: list[dict], flash_docs: list[dict], model: str, backend: str) -> dict:
    backend = (backend or "anthropic").lower()
    if backend == "vertex":
        loc = os.environ.get("VERTEX_CLAUDE_LOCATION", "global")
        model = model or os.environ.get("VERTEX_CLAUDE_MODEL", "claude-sonnet-5")
        return sonnet_via_vertex(projects, flash_docs, model, loc)
    # Anthropic direct (default until Vertex quota approved)
    model = model or "claude-sonnet-5"
    return sonnet_via_anthropic(projects, flash_docs, model)


# ---------------------------------------------------------------------------
# Step 4 — verify
# ---------------------------------------------------------------------------

def verify_url(url: str, timeout: int = 25) -> dict:
    result = {
        "url": url,
        "ok": False,
        "status": None,
        "content_type": "",
        "resolved_url": url,
        "verify_kind": "failed",
        "bytes": None,
    }
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Range": "bytes=0-2047"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read(2048)
            ctype = resp.headers.get("Content-Type", "")
            final = resp.geturl()
            code = getattr(resp, "status", None) or resp.getcode()
            result.update(
                {
                    "ok": 200 <= int(code) < 400,
                    "status": int(code),
                    "content_type": ctype,
                    "resolved_url": final,
                    "bytes": len(data),
                }
            )
            path = urllib.parse.urlparse(final).path.lower()
            is_file = any(path.endswith(ext) for ext in DOC_EXTENSIONS)
            ctype_l = ctype.lower()
            if is_file or any(
                x in ctype_l for x in ("pdf", "zip", "msword", "officedocument", "octet-stream")
            ):
                result["verify_kind"] = "verified_doc"
            elif "html" in ctype_l or data[:15].lower().startswith(b"<!doctype") or data[:5].lower().startswith(
                b"<html"
            ):
                result["verify_kind"] = "html_page"
            else:
                result["verify_kind"] = "other"
    except Exception as e:
        result["error"] = str(e)
    return result


def verify_docs(docs: list[dict]) -> list[dict]:
    out = []
    for i, d in enumerate(docs, 1):
        url = d.get("url") or ""
        print(f"[verify] {i}/{len(docs)} {url[:90]}", file=sys.stderr)
        v = verify_url(url)
        merged = dict(d)
        merged["verify_ok"] = v["ok"]
        merged["verify_kind"] = v["verify_kind"]
        merged["resolved_url"] = v.get("resolved_url") or url
        merged["content_type"] = v.get("content_type") or ""
        if v.get("error"):
            merged["verify_error"] = v["error"]
        out.append(merged)
        time.sleep(0.25)
    return out


def build_page_payload(
    socrata: dict | None,
    enrichment_projects: list[dict],
    flash_docs: list[dict],
    sonnet_docs: list[dict],
    verified: list[dict],
    sonnet_backend: str,
) -> dict:
    by_id: dict[str, dict] = {}

    # Browse list: Socrata page set first (projects-like corpus)
    for p in (socrata or {}).get("projects") or []:
        by_id[p["id"]] = {
            "id": p["id"],
            "name": p.get("name") or "",
            "city": p.get("city") or "",
            "county": p.get("county") or "",
            "owner": p.get("owner") or "",
            "project_type": p.get("project_type") or "",
            "status": p.get("status") or "permitting",
            "opened_or_announced_date": p.get("opened_or_announced_date") or "",
            "estimated_value_usd": p.get("estimated_value_usd"),
            "square_footage": p.get("square_footage"),
            "origin": "socrata",
            "flash_doc_count": 0,
            "sonnet_kept_count": 0,
            "verified_doc_count": 0,
            "html_page_count": 0,
            "downloaded_count": 0,
            "documents": [],
        }

    for p in enrichment_projects:
        pid = p["id"]
        if pid not in by_id:
            by_id[pid] = {
                "id": pid,
                "name": p.get("name") or "",
                "city": p.get("city") or "",
                "county": p.get("county") or "",
                "owner": p.get("owner") or "",
                "project_type": p.get("project_type") or "",
                "status": "planning",
                "opened_or_announced_date": p.get("opened_or_announced_date") or "",
                "estimated_value_usd": None,
                "square_footage": None,
                "origin": p.get("origin") or "curated",
                "flash_doc_count": 0,
                "sonnet_kept_count": 0,
                "verified_doc_count": 0,
                "html_page_count": 0,
                "downloaded_count": 0,
                "documents": [],
            }
        else:
            by_id[pid]["origin"] = "socrata+enrichment"

    for d in flash_docs:
        pid = d.get("project_id")
        if pid in by_id:
            by_id[pid]["flash_doc_count"] += 1

    for d in sonnet_docs:
        pid = d.get("project_id")
        if pid in by_id:
            by_id[pid]["sonnet_kept_count"] += 1

    verified_docs = [d for d in verified if d.get("verify_kind") == "verified_doc"]
    for d in verified:
        pid = d.get("project_id") or "unknown"
        if pid not in by_id:
            by_id[pid] = {
                "id": pid,
                "name": d.get("project_name") or pid,
                "city": "",
                "county": "",
                "owner": "",
                "project_type": "",
                "status": "planning",
                "opened_or_announced_date": "",
                "estimated_value_usd": None,
                "square_footage": None,
                "origin": "enrichment",
                "flash_doc_count": 0,
                "sonnet_kept_count": 0,
                "verified_doc_count": 0,
                "html_page_count": 0,
                "downloaded_count": 0,
                "documents": [],
            }
        entry = {
            "title": d.get("title") or "",
            "url": d.get("resolved_url") or d.get("url") or "",
            "doc_type": d.get("doc_type") or "",
            "confidence": d.get("confidence"),
            "verify_kind": d.get("verify_kind"),
            "content_type": d.get("content_type") or "",
            "action": d.get("action") or "kept",
            "notes": d.get("notes") or "",
            "source_pass": d.get("source_pass") or "sonnet",
        }
        by_id[pid]["documents"].append(entry)
        if d.get("verify_kind") == "verified_doc":
            by_id[pid]["verified_doc_count"] += 1
        elif d.get("verify_kind") == "html_page":
            by_id[pid]["html_page_count"] += 1

    rows = sorted(
        by_id.values(),
        key=lambda r: (
            -r["verified_doc_count"],
            -r["sonnet_kept_count"],
            -(r.get("estimated_value_usd") or 0),
            r["name"],
        ),
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "socrata -> gemini_flash -> sonnet_dedupe -> exact_url_hash -> http_verify",
        "sonnet_backend": sonnet_backend,
        "policy": "Socrata first; Flash gathers only; Sonnet owns semantic dedupe/golden records; code hash is post-Sonnet safety net",
        "socrata": {
            "total_commercial": (socrata or {}).get("total_commercial") or 0,
            "months": (socrata or {}).get("months"),
            "cutoff": (socrata or {}).get("cutoff"),
            "dataset": "data.nj.gov/w9se-dmra",
        },
        "stats": {
            "socrata_total": (socrata or {}).get("total_commercial") or 0,
            "page_projects": len(rows),
            "enrichment_projects": len(enrichment_projects),
            "flash_raw": len(flash_docs),
            "sonnet_kept": len(sonnet_docs),
            "verified_docs": len(verified_docs),
            "html_pages": sum(1 for d in verified if d.get("verify_kind") == "html_page"),
            "failed": sum(1 for d in verified if d.get("verify_kind") == "failed"),
        },
        "projects": rows,
    }


def write_download_list(verified: list[dict]) -> list[dict]:
    rows = []
    for d in verified:
        if d.get("verify_kind") != "verified_doc":
            continue
        rows.append(
            {
                "model": "flash-sonnet-pipeline",
                "project_id": d.get("project_id") or "unknown",
                "project_name": d.get("project_name") or "",
                "title": d.get("title") or "",
                "doc_type": d.get("doc_type") or "",
                "url": d.get("resolved_url") or d.get("url"),
                "notes": d.get("notes") or "",
            }
        )
    DOWNLOAD_LIST.write_text(
        json.dumps({"documents": rows, "generated_at": date.today().isoformat()}, indent=2) + "\n"
    )
    return rows


def run_download(rows: list[dict]) -> dict:
    shared = OUT_DIR / "nj-2026-docs-to-download.json"
    previous = shared.read_text() if shared.exists() else None
    shared.write_text(json.dumps({"documents": rows, "generated_at": date.today().isoformat()}, indent=2) + "\n")
    try:
        spec = importlib.util.spec_from_file_location(
            "fetch_nj_documents", ROOT / "scripts" / "fetch-nj-documents.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rc = mod.main()
        return {"exit_code": rc, "manifest": str(ROOT / "data" / "documents" / "new-jersey" / "manifest.json")}
    finally:
        if previous is not None:
            shared.write_text(previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Limit enrichment project count (0 = all curated)")
    parser.add_argument("--socrata-months", type=int, default=6)
    parser.add_argument("--socrata-page-cap", type=int, default=500)
    parser.add_argument("--include-socrata-top", type=int, default=0, help="Also enrich top N Socrata by value")
    parser.add_argument("--skip-socrata", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-flash", action="store_true")
    parser.add_argument("--skip-sonnet", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--flash-model", default="")
    parser.add_argument(
        "--sonnet-backend",
        default="",
        help="anthropic (default) or vertex. Env VERTEX_CLAUDE_BACKEND overrides empty.",
    )
    parser.add_argument("--sonnet-model", default="")
    args = parser.parse_args()

    load_env()

    # Step 0: Socrata
    if args.skip_socrata and SOCRATA_SNAP.exists():
        socrata = json.loads(SOCRATA_SNAP.read_text())
        print(f"[socrata] reused snapshot total={socrata.get('total_commercial')}", file=sys.stderr)
    else:
        socrata = pull_socrata(months=args.socrata_months, page_cap=args.socrata_page_cap)

    projects = load_enrichment_projects(limit=args.limit, include_socrata_top=args.include_socrata_top)
    print(f"[enrich] projects for Flash/Sonnet: {len(projects)}", file=sys.stderr)

    # Settings already resolves NJ_DCA_FLASH_MODEL / VERTEX_GEMINI_MODEL and
    # carries the repo default; do not re-hardcode a version here.
    from state_agent_pipeline.config import Settings as _S  # noqa: PLC0415
    flash_model = args.flash_model or _S.from_env().flash_model
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "specindex-ai")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    sonnet_backend = (
        args.sonnet_backend
        or os.environ.get("VERTEX_CLAUDE_BACKEND")
        or "anthropic"
    ).lower()
    if sonnet_backend == "vertex":
        sonnet_model = args.sonnet_model or os.environ.get("VERTEX_CLAUDE_MODEL", "claude-sonnet-5")
    else:
        sonnet_model = args.sonnet_model or "claude-sonnet-5"

    if args.skip_llm:
        flash = json.loads(FLASH_RAW.read_text()) if FLASH_RAW.exists() else {"documents": []}
        sonnet = json.loads(SONNET_RAW.read_text()) if SONNET_RAW.exists() else {"documents": []}
        # Pass Flash list intact to page stats; Sonnet already owned dedupe in prior run
        flash_docs = list(flash.get("documents") or [])
        sonnet_docs = sonnet.get("documents") or []
    else:
        # Step 1: Gemini Flash (Model A) — gather only, no dedupe
        if args.skip_flash and FLASH_RAW.exists():
            flash = json.loads(FLASH_RAW.read_text())
        else:
            flash = flash_gather(projects, flash_model, gcp_project, location)
            FLASH_RAW.write_text(json.dumps({k: v for k, v in flash.items() if k != "raw_text"}, indent=2) + "\n")
            (OUT_DIR / "nj-flash-sonnet-pipeline-flash-raw.txt").write_text(flash.get("raw_text") or "")
        flash_docs = list(flash.get("documents") or [])
        print(f"[flash] raw candidates (no dedupe)={len(flash_docs)}", file=sys.stderr)

        # Step 2: Sonnet (Model B) — owns semantic dedupe + golden records
        if args.skip_sonnet and SONNET_RAW.exists():
            sonnet = json.loads(SONNET_RAW.read_text())
            sonnet_docs = sonnet.get("documents") or []
            sonnet_backend = sonnet.get("backend") or sonnet_backend
        else:
            sonnet = sonnet_audit(projects, flash_docs, sonnet_model, sonnet_backend)
            SONNET_RAW.write_text(
                json.dumps({k: v for k, v in sonnet.items() if k != "raw_text"}, indent=2) + "\n"
            )
            (OUT_DIR / "nj-flash-sonnet-pipeline-sonnet-raw.txt").write_text(sonnet.get("raw_text") or "")
            sonnet_docs = sonnet.get("documents") or []
            sonnet_backend = sonnet.get("backend") or sonnet_backend
        print(f"[sonnet] backend={sonnet_backend} kept after Sonnet dedupe={len(sonnet_docs)}", file=sys.stderr)

    # Exact URL hash only after Sonnet (safety net for identical strings)
    before = len(sonnet_docs)
    sonnet_docs = code_dedupe(sonnet_docs)
    if len(sonnet_docs) != before:
        print(f"[code] post-Sonnet exact-URL collapse {before} -> {len(sonnet_docs)}", file=sys.stderr)
    verified = verify_docs(sonnet_docs)
    VERIFIED.write_text(json.dumps({"documents": verified, "generated_at": date.today().isoformat()}, indent=2) + "\n")

    download_rows = write_download_list(verified)
    page = build_page_payload(socrata, projects, flash_docs, sonnet_docs, verified, sonnet_backend)
    PAGE_SUMMARY.write_text(json.dumps(page, indent=2) + "\n")
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_JSON.write_text(json.dumps(page, indent=2) + "\n")

    print(json.dumps(page["stats"], indent=2))
    print(f"Wrote {PUBLIC_JSON}")
    print(f"Download candidates: {len(download_rows)}")

    if args.download and download_rows:
        info = run_download(download_rows)
        print(f"Download exit={info['exit_code']} manifest={info['manifest']}")
        manifest_path = ROOT / "data" / "documents" / "new-jersey" / "manifest.json"
        if manifest_path.exists():
            man = json.loads(manifest_path.read_text())
            by_project = man.get("by_project") or {}
            for p in page["projects"]:
                entry = by_project.get(p["id"]) or {}
                docs = entry.get("documents") or []
                linked = entry.get("linked_documents") or []
                p["downloaded_count"] = len(docs) + len(linked)
            page["stats"]["files_downloaded"] = man.get("files_downloaded") or 0
            page["stats"]["download_projects"] = man.get("projects") or 0
            PAGE_SUMMARY.write_text(json.dumps(page, indent=2) + "\n")
            PUBLIC_JSON.write_text(json.dumps(page, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
