"""SAM.gov bulk-CSV ingestion provider.

Unlike Socrata/ArcGIS, SAM.gov has no per-state query API for Contract
Opportunities -- it publishes a single nationwide daily CSV snapshot
(no auth, no quota, ~230MB, ~80k rows), and every consumer filters
client-side. So "per-state" here means "download once, filter to this
state's PopState + NAICS whitelist," not a scoped remote query.

Ported from scripts/pull-sam-gov-bulk-ga.py (verified live 2026-07-25:
cp1252 encoding, not UTF-8 -- utf-8 decoding fails outright on byte 0xb7)
into the BaseIngestionProvider interface so it gets the same incremental-
watermark treatment as the other state agents, instead of always
reprocessing all ~80k rows from scratch every run.

Deliberately has no Flash/Sonnet involvement downstream -- this is clean
structured government data (title, NAICS code, dates, dollar-free
solicitation metadata), not messy free-text needing LLM extraction.
to_projects() below is the same deterministic field mapping the old
script used, ported as-is (not reinvented) since it was already verified
against real data.
"""

from __future__ import annotations

import csv
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .base_provider import BaseIngestionProvider
from .hashing import hash_fields

BULK_URL = "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/ContractOpportunitiesFullCSV.csv"

# Matches scripts/pull-sam-gov-bulk-ga.py -- building construction only,
# excludes highway/civil NAICS codes.
DEFAULT_NAICS_CODES = {
    "236220": "commercial",
    "236210": "industrial",
}

STATUS_BY_TYPE = {
    "Presolicitation": "planning",
    "Sources Sought": "planning",
    "Special Notice": "planning",
    "Solicitation": "bidding",
    "Combined Synopsis/Solicitation": "bidding",
    "Modification/Amendment/Cancel": "bidding",
    "Award Notice": "under_construction",
}

COMPETITOR_WATCH_DEFAULT = {
    "commercial": ["glazing", "hvac", "roofing", "lighting", "flooring", "doors and hardware", "fire suppression"],
    "industrial": ["roofing", "hvac", "dock equipment", "concrete", "lighting", "fire suppression", "switchgear"],
}


class SamGovProvider(BaseIngestionProvider):
    def __init__(
        self,
        *,
        state_code: str,
        naics_codes: dict[str, str] | None = None,
        cache_path: Path | None = None,
        cache_max_age_hours: float = 20.0,
        max_retries: int = 3,
    ) -> None:
        self.state_code = state_code.upper()
        self.naics_codes = naics_codes or DEFAULT_NAICS_CODES
        self.cache_path = cache_path or (
            Path(__file__).resolve().parents[4] / "data" / "raw" / ".sam-gov-bulk-download.csv"
        )
        self.cache_max_age_hours = cache_max_age_hours
        self.max_retries = max_retries

    def _ensure_csv(self) -> Path:
        if self.cache_path.exists():
            age_hours = (time.time() - self.cache_path.stat().st_mtime) / 3600
            if age_hours < self.cache_max_age_hours:
                print(f"[sam-gov] reusing cached CSV ({age_hours:.1f}h old)", file=sys.stderr)
                return self.cache_path

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                print(f"[sam-gov] downloading {BULK_URL} (~230MB, no auth)...", file=sys.stderr)
                req = urllib.request.Request(BULK_URL, headers={"User-Agent": "SpecIndex-StateAgent/0.2"})
                with urllib.request.urlopen(req, timeout=300) as resp, open(self.cache_path, "wb") as f:
                    while chunk := resp.read(1 << 20):
                        f.write(chunk)
                print(f"[sam-gov] downloaded {self.cache_path.stat().st_size:,} bytes", file=sys.stderr)
                return self.cache_path
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last_err = e
                wait = min(60, (2**attempt) * 5)
                print(f"[sam-gov] retry {attempt + 1}/{self.max_retries}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError(f"SAM.gov bulk CSV download failed after {self.max_retries} retries: {last_err}")

    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        # State.last_processed_id defaults to "0" -- not a valid date,
        # treat same as "no watermark yet" (see usaspending_provider.py).
        last_watermark = "" if last_watermark in (None, "", "0") else last_watermark
        csv_path = self._ensure_csv()
        csv.field_size_limit(10_000_000)
        rows: list[dict[str, Any]] = []
        # cp1252, not utf-8 -- confirmed 2026-07-25, utf-8 fails outright
        # on byte 0xb7; utf-8+errors=replace "works" but mangles em-dashes.
        with open(csv_path, encoding="cp1252") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("PopState") != self.state_code:
                    continue
                if row.get("NaicsCode") not in self.naics_codes:
                    continue
                posted = (row.get("PostedDate") or "")[:10]
                if last_watermark and posted and posted <= last_watermark:
                    continue
                rows.append(row)
        print(f"[sam-gov:{self.state_code}] {len(rows)} matching rows (watermark={last_watermark!r})", file=sys.stderr)
        return rows

    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        return hash_fields(row, ["NoticeId"])

    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        dates = [(r.get("PostedDate") or "")[:10] for r in rows if r.get("PostedDate")]
        dates = [d for d in dates if d]
        if not dates:
            return current
        return max([current] + dates) if current else max(dates)

    def to_projects(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deterministic mapping to SpecIndex project dicts -- ported
        as-is from pull-sam-gov-bulk-ga.py's to_project(), not routed
        through Flash/Sonnet (no free text here worth an LLM's judgment)."""
        from project_identity import slugify

        out = []
        for row in rows:
            notice_id = row["NoticeId"]
            # SAM.gov mints a NEW NoticeId every time a solicitation is
            # amended or reposted, while Sol# (the actual solicitation
            # number) stays constant across those amendments -- keying the
            # project id on notice_id alone made every amendment a brand
            # new project row. Found 2026-08-07/08: one VA solicitation
            # (Y1DZ Building 9A EHRM, Dublin GA) had 7 separate project
            # rows, one per amendment, each with a different partial
            # document set. Sol# is not always present on every row, so
            # fall back to notice_id only when it's genuinely missing --
            # that subset still duplicates on amendment, but the majority
            # (this one included) now dedupe correctly. A one-time cleanup
            # of ALREADY-duplicated rows created before this fix is a
            # separate, deliberately deferred step (see docs/ROADMAP.md) --
            # this only stops NEW duplicates from forming.
            dedup_key = (row.get("Sol#") or "").strip() or notice_id
            naics = row.get("NaicsCode", "")
            project_type = self.naics_codes.get(naics, "commercial")
            notice_type = row.get("Type", "")
            slug = slugify(row.get("Title", "untitled"))[:50]
            city = (row.get("PopCity") or "").strip()
            posted = (row.get("PostedDate") or "")[:10]
            deadline = (row.get("ResponseDeadLine") or "")[:10]

            desc_parts = [
                f"Federal {notice_type.lower()} {row.get('Sol#', '')}".strip(),
                row.get("Title", ""),
            ]
            if deadline:
                desc_parts.append(f"Response deadline {deadline}")
            description = ". ".join(p.rstrip(".") for p in desc_parts if p) + "."

            key_specs = [f"NAICS {naics}", f"Notice type: {notice_type}"]
            if row.get("SetASide"):
                key_specs.append(row["SetASide"])
            if row.get("ClassificationCode"):
                key_specs.append(f"Classification code {row['ClassificationCode']}")

            out.append(
                {
                    "id": f"{self.state_code.lower()}-sam-{slugify(dedup_key)[:24]}-{slug}",
                    "name": (row.get("Title") or "Untitled")[:120],
                    "city": city,
                    "county": "",
                    "status": STATUS_BY_TYPE.get(notice_type, "planning"),
                    "project_type": project_type,
                    "estimated_value_usd": None,
                    "square_footage": None,
                    "owner": (row.get("Department/Ind.Agency") or "").title(),
                    "architect": "",
                    "general_contractor": (row.get("Awardee") or "").title() if row.get("Awardee") else "",
                    "opened_or_announced_date": posted or None,
                    "description": description[:900],
                    "key_specs": key_specs,
                    "mentioned_brands": [],
                    "competitor_watch": COMPETITOR_WATCH_DEFAULT.get(
                        project_type, ["hvac", "roofing", "lighting", "concrete"]
                    ),
                    "sources": [
                        {
                            "title": f"SAM.gov {notice_type} {row.get('Sol#', notice_id)}",
                            "url": row.get("Link", ""),
                        }
                    ],
                    "open_for": (
                        "Federal solicitation, bid package open. Product substitution requests may still be "
                        "possible before award -- note: no attachment links in the bulk extract, check the "
                        "notice page directly for spec/drawing documents."
                        if notice_type in {"Solicitation", "Combined Synopsis/Solicitation"}
                        else "Presolicitation/sources-sought notice -- spec window not yet finalized, "
                        "earliest point to reach the design team."
                    ),
                    "state": self.state_code,
                }
            )
        return out
