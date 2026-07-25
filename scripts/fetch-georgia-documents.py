#!/usr/bin/env python3
"""Fetch HTML snapshots and linked documents from Georgia project source URLs."""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "georgia-commercial-projects.json"
OUT_DIR = ROOT / "data" / "documents" / "georgia"
MANIFEST = OUT_DIR / "manifest.json"

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


def fetch(url: str, timeout: int = 30) -> tuple[bytes, str, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        final = resp.geturl()
        return data, ctype, final


def safe_name(text: str, max_len: int = 80) -> str:
    text = re.sub(r"[^\w\- .]+", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "-", text.strip())
    return text[:max_len] or "file"


def ext_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in DOC_EXTENSIONS:
        if path.endswith(ext):
            return ext
    return ""


def is_document_url(url: str) -> bool:
    return bool(ext_from_url(url))


def extract_links(html: str, base_url: str) -> list[str]:
    hrefs = re.findall(r"""href=["']([^"'#]+)["']""", html, flags=re.I)
    out: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        href = href.strip()
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        abs_url = urllib.parse.urljoin(base_url, href)
        abs_url = abs_url.split("#")[0]
        if abs_url not in seen:
            seen.add(abs_url)
            out.append(abs_url)
    return out


def guess_filename(url: str, content_type: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = Path(path).name
    if name and "." in name:
        return safe_name(name)
    ext = ext_from_url(url)
    if not ext and "pdf" in content_type.lower():
        ext = ".pdf"
    if not ext and "html" in content_type.lower():
        ext = ".html"
    return f"download{ext or '.bin'}"


def save_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def harvest_project(project: dict) -> dict:
    pid = project["id"]
    project_dir = OUT_DIR / pid
    project_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "project_id": pid,
        "project_name": project["name"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "documents": [],
        "errors": [],
    }

    sources = project.get("sources") or []
    urls = []
    for s in sources:
        u = (s.get("url") or "").strip()
        if u and u not in urls:
            urls.append(u)

    if not urls:
        result["errors"].append("no_source_urls")
        save_bytes(project_dir / "manifest.json", json.dumps(result, indent=2).encode())
        return result

    all_doc_links: set[str] = set()

    for idx, url in enumerate(urls, start=1):
        source_entry = {"url": url, "title": sources[0].get("title", ""), "files": []}
        try:
            data, ctype, final_url = fetch(url)
            html_name = f"source-{idx:02d}.html"
            if "html" in ctype.lower() or data[:15].lower().startswith(b"<!doctype") or data[:5].lower().startswith(b"<html"):
                save_bytes(project_dir / html_name, data)
                source_entry["files"].append(html_name)
                html = data.decode("utf-8", errors="replace")
                for link in extract_links(html, final_url or url):
                    if is_document_url(link):
                        all_doc_links.add(link)
            elif is_document_url(final_url or url):
                fname = guess_filename(final_url or url, ctype)
                save_bytes(project_dir / fname, data)
                source_entry["files"].append(fname)
                result["documents"].append(
                    {"filename": fname, "url": final_url or url, "content_type": ctype}
                )
            else:
                # Save unknown content types as snapshot
                fname = f"source-{idx:02d}.bin"
                save_bytes(project_dir / fname, data)
                source_entry["files"].append(fname)
            source_entry["final_url"] = final_url or url
            source_entry["content_type"] = ctype
        except urllib.error.HTTPError as e:
            source_entry["error"] = f"HTTP {e.code}"
            result["errors"].append(f"{url}: HTTP {e.code}")
        except Exception as e:
            source_entry["error"] = str(e)
            result["errors"].append(f"{url}: {e}")
        result["sources"].append(source_entry)
        time.sleep(0.5)

    # Download discovered document links
    for doc_idx, doc_url in enumerate(sorted(all_doc_links), start=1):
        try:
            data, ctype, final_url = fetch(doc_url)
            fname = f"doc-{doc_idx:02d}-{guess_filename(final_url or doc_url, ctype)}"
            save_bytes(project_dir / fname, data)
            result["documents"].append(
                {
                    "filename": fname,
                    "url": final_url or doc_url,
                    "content_type": ctype,
                    "size_bytes": len(data),
                }
            )
        except Exception as e:
            result["errors"].append(f"doc {doc_url}: {e}")
        time.sleep(0.5)

    save_bytes(project_dir / "manifest.json", json.dumps(result, indent=2).encode())
    return result


def main() -> None:
    corpus = json.loads(CORPUS.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []
    total_docs = 0
    for project in corpus["projects"]:
        print(f"Harvesting {project['id']}...")
        r = harvest_project(project)
        all_results.append(r)
        total_docs += len(r["documents"])
        print(f"  docs={len(r['documents'])} errors={len(r['errors'])}")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_count": len(all_results),
        "total_documents": total_docs,
        "projects_with_documents": sum(1 for r in all_results if r["documents"]),
        "projects_with_errors": sum(1 for r in all_results if r["errors"]),
        "projects_without_urls": sum(
            1 for r in all_results if "no_source_urls" in r["errors"]
        ),
        "projects": all_results,
    }
    MANIFEST.write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"\nDone: {summary['total_documents']} documents across "
        f"{summary['projects_with_documents']} projects "
        f"({summary['projects_without_urls']} without URLs)"
    )


if __name__ == "__main__":
    main()
