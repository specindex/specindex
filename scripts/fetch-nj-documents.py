#!/usr/bin/env python3
"""Download verified NJ construction documents into data/documents/new-jersey/.

Reads the union of Sonnet + Gemini verified durable URLs from
data/raw/nj-2026-docs-to-download.json (or rebuilds from rescored raw files).

Also crawls downloaded HTML/PDF-adjacent listing pages for linked .pdf/.zip
files that may include project manuals / CSI spec books.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "documents" / "new-jersey"
MANIFEST = OUT_DIR / "manifest.json"
DOWNLOAD_LIST = ROOT / "data" / "raw" / "nj-2026-docs-to-download.json"
SONNET = ROOT / "data" / "raw" / "nj-2026-docs-sonnet.json"
GEMINI = ROOT / "data" / "raw" / "nj-2026-docs-gemini-flash.json"

DOC_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".dwg",
    ".dxf",
    ".rvt",
    ".ifc",
}

USER_AGENT = (
    "SpecIndexDocumentBot/1.0 (+https://specindex.ai; research/archival; "
    "contact hello@specindex.ai)"
)

ctx = ssl.create_default_context()

CSI_HINTS = re.compile(
    r"spec(?:ification)?s?|project\s+manual|division\s*0?[1-9]|csi\s*masterformat|"
    r"bid\s+package|drawing\s+set|addendum|volume\s+[iivx]+",
    re.I,
)


def fetch(url: str, timeout: int = 60) -> tuple[bytes, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read(), resp.headers.get("Content-Type", ""), resp.geturl()


def safe_name(text: str, max_len: int = 100) -> str:
    text = re.sub(r"[^\w\- .]+", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:max_len] or "file"


def ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in DOC_EXTENSIONS:
        if path.endswith(ext):
            return ext
    return ""


def guess_filename(url: str, content_type: str, fallback: str = "download") -> str:
    path = urllib.parse.urlparse(url).path
    name = Path(urllib.parse.unquote(path)).name
    if name and "." in name:
        return safe_name(name)
    ext = ext_from_url(url)
    if not ext and "pdf" in (content_type or "").lower():
        ext = ".pdf"
    if not ext and "zip" in (content_type or "").lower():
        ext = ".zip"
    return f"{safe_name(fallback)}{ext or '.bin'}"


def extract_links(html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r"""href=["']([^"'#]+)["']""", html, flags=re.I)
    out: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        href = href.strip()
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        abs_url = urllib.parse.urljoin(base_url, href).split("#")[0]
        if abs_url not in seen:
            seen.add(abs_url)
            out.append(abs_url)
    return out


def build_download_list() -> list[dict]:
    if DOWNLOAD_LIST.exists():
        return list(json.loads(DOWNLOAD_LIST.read_text()).get("documents") or [])
    rows: list[dict] = []
    for model, path in (("sonnet", SONNET), ("gemini", GEMINI)):
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for doc in data.get("documents_rescored") or []:
            if doc.get("verify_kind") != "verified_doc":
                continue
            rows.append(
                {
                    "model": model,
                    "project_id": doc.get("project_id") or "unknown",
                    "project_name": doc.get("project_name") or "",
                    "title": doc.get("title") or "",
                    "doc_type": doc.get("doc_type") or "",
                    "url": doc.get("resolved_url") or doc.get("url"),
                    "notes": doc.get("notes") or "",
                }
            )
    return rows


def looks_like_csi(name: str, notes: str, url: str) -> bool:
    blob = f"{name} {notes} {url}"
    return bool(CSI_HINTS.search(blob))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = build_download_list()
    # Dedupe by URL, keep first model attribution
    by_url: dict[str, dict] = {}
    for d in docs:
        url = (d.get("url") or "").strip()
        if url and url not in by_url:
            by_url[url] = d

    projects: dict[str, dict] = {}
    top_errors: list[str] = []
    downloaded = 0
    csi_candidates = 0

    for url, meta in by_url.items():
        pid = meta.get("project_id") or "unknown"
        project_dir = OUT_DIR / pid
        project_dir.mkdir(parents=True, exist_ok=True)
        entry = projects.setdefault(
            pid,
            {
                "project_id": pid,
                "project_name": meta.get("project_name") or "",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "models": [],
                "documents": [],
                "linked_documents": [],
                "errors": [],
                "csi_candidate_count": 0,
            },
        )
        model = meta.get("model") or ""
        if model and model not in entry["models"]:
            entry["models"].append(model)

        try:
            data, ctype, final = fetch(url)
            fname = guess_filename(final or url, ctype, fallback=meta.get("title") or "doc")
            # Avoid collisions
            dest = project_dir / fname
            if dest.exists():
                stem, suf = dest.stem, dest.suffix
                dest = project_dir / f"{stem}-{model or 'x'}{suf}"
            dest.write_bytes(data)
            downloaded += 1
            is_csi = looks_like_csi(meta.get("title") or "", meta.get("notes") or "", final or url)
            if is_csi:
                csi_candidates += 1
                entry["csi_candidate_count"] += 1
            rec = {
                "filename": dest.name,
                "url": final or url,
                "source_model": model,
                "doc_type": meta.get("doc_type") or "",
                "title": meta.get("title") or "",
                "content_type": ctype,
                "size_bytes": len(data),
                "csi_candidate": is_csi,
            }
            entry["documents"].append(rec)

            # If HTML, harvest linked document files
            if "html" in ctype.lower() or data[:15].lower().startswith(b"<!doctype") or data[:5].lower().startswith(b"<html"):
                html = data.decode("utf-8", errors="replace")
                for link in extract_links(html, final or url):
                    if not ext_from_url(link):
                        continue
                    try:
                        d2, c2, f2 = fetch(link)
                        fname2 = f"linked-{guess_filename(f2 or link, c2)}"
                        dest2 = project_dir / fname2
                        if not dest2.exists():
                            dest2.write_bytes(d2)
                        is_csi2 = looks_like_csi(fname2, "", f2 or link)
                        if is_csi2:
                            csi_candidates += 1
                            entry["csi_candidate_count"] += 1
                        entry["linked_documents"].append(
                            {
                                "filename": dest2.name,
                                "url": f2 or link,
                                "content_type": c2,
                                "size_bytes": len(d2),
                                "csi_candidate": is_csi2,
                                "via": final or url,
                            }
                        )
                        time.sleep(0.3)
                    except Exception as e:
                        entry["errors"].append(f"linked {link}: {e}")
        except Exception as e:
            msg = f"{url}: {e}"
            entry["errors"].append(msg)
            top_errors.append(msg)
        time.sleep(0.4)

        # Per-project manifest
        (project_dir / "manifest.json").write_text(json.dumps(entry, indent=2) + "\n")

    summary = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source_list": str(DOWNLOAD_LIST.relative_to(ROOT)) if DOWNLOAD_LIST.exists() else "rescored raw",
        "unique_urls": len(by_url),
        "files_downloaded": downloaded,
        "projects": len(projects),
        "csi_candidate_files": csi_candidates,
        "note": (
            "csi_candidate is a filename/title heuristic only. "
            "True CSI MasterFormat project manuals are rare in public NJ feeds; "
            "NJSDA RFPs usually point to full bid sets behind portals."
        ),
        "errors": top_errors[:50],
        "by_project": projects,
    }
    MANIFEST.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Downloaded {downloaded} files across {len(projects)} projects -> {OUT_DIR}")
    print(f"CSI-title heuristic hits: {csi_candidates}")
    print(f"Manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
