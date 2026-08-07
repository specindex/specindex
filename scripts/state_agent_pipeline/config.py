"""Config and env loading for the NJ DCA pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIPELINE_DIR = ROOT / "data" / "pipeline" / "nj-dca"
STATE_PATH = PIPELINE_DIR / "state.json"
RAW_DIR = PIPELINE_DIR / "raw"
EXTRACTED_DIR = PIPELINE_DIR / "extracted"
GOLDEN_DIR = PIPELINE_DIR / "golden"

SOCRATA_DOMAIN = "data.nj.gov"
SOCRATA_DATASET = "w9se-dmra"

# Confirmed live commercial use groups (see scripts/pull-nj-dca.py).
COMMERCIAL_USE_GROUPS = [
    "Business Uses",
    "Mercantile buildings",
    "Restaurants/Night Clubs",
    "Hotels/motels",
    "Educational",
    "Factory and industrial (low hazard)",
    "Factory and industrial (moderate hazard)",
    "Storage (low hazard)",
    "Storage (moderate hazard)",
    "Institutional",
]


def load_env(root: Path | None = None) -> None:
    env_path = (root or ROOT) / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    google_cloud_project: str
    google_cloud_location: str
    flash_model: str
    # Explicit Gemini Pro handle for the reasoning-heavy steps. Distinct from
    # sonnet_model, which is a BACKEND-dependent slot that may resolve to
    # Claude or to Gemini Pro depending on NJ_DCA_SONNET_BACKEND. Steps that
    # genuinely need Pro must not have their model silently swapped for Claude
    # by an unrelated backend setting.
    pro_model: str
    sonnet_backend: str  # anthropic | vertex | gemini_pro
    sonnet_model: str
    anthropic_api_key: str | None
    socrata_app_token: str | None
    flash_batch_size: int = 40
    # 60 was the original NJ-only default and worked fine in small manual
    # tests (5-10 rows), but real full-size cloud runs (2026-07-27, 30-day
    # NJ lookback) showed EVERY Sonnet batch at size 60 failing to parse
    # ("Expecting ',' delimiter" at a consistent offset -- max_tokens=16000
    # truncation, not a fluke). Real per-record JSON verbosity at full
    # batch size exceeds what small manual tests ever exercised. Dropped
    # to 25 so a batch's expected output comfortably fits under the token
    # cap regardless of per-record verbosity.
    sonnet_batch_size: int = 25
    max_retries: int = 4

    @classmethod
    def from_env(cls) -> "Settings":
        load_env()
        backend = (os.environ.get("NJ_DCA_SONNET_BACKEND") or os.environ.get("VERTEX_CLAUDE_BACKEND") or "anthropic").lower()
        if backend == "vertex":
            sonnet_model = os.environ.get("VERTEX_CLAUDE_MODEL") or "claude-sonnet-5"
        elif backend == "gemini_pro":
            sonnet_model = os.environ.get("VERTEX_GEMINI_PRO_MODEL") or "gemini-2.5-pro"
        else:
            sonnet_model = os.environ.get("NJ_DCA_SONNET_MODEL") or "claude-sonnet-5"
        return cls(
            google_cloud_project=os.environ.get("GOOGLE_CLOUD_PROJECT") or "specindex-ai",
            google_cloud_location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global",
            flash_model=os.environ.get("NJ_DCA_FLASH_MODEL")
            or os.environ.get("VERTEX_GEMINI_MODEL")
            or "gemini-3.6-flash",
            # Gemini 3.1 Pro, per Asif 2026-08-05. The PUBLISHED name on this
            # Vertex project is "gemini-3.1-pro-preview" -- the bare
            # "gemini-3.1-pro" returns 404 NOT_FOUND, as do gemini-3.0/3.5/3.6-pro.
            # Probed live rather than assumed; a wrong model name here would
            # fail only at first use, deep inside a batch run.
            # Stable fallback if the preview is withdrawn: gemini-2.5-pro.
            pro_model=os.environ.get("VERTEX_GEMINI_PRO_MODEL") or "gemini-3.1-pro-preview",
            sonnet_backend=backend,
            sonnet_model=sonnet_model,
            socrata_app_token=os.environ.get("SOCRATA_APP_TOKEN"),
            flash_batch_size=int(os.environ.get("NJ_DCA_FLASH_BATCH") or 40),
            sonnet_batch_size=int(os.environ.get("NJ_DCA_SONNET_BATCH") or 25),
            max_retries=int(os.environ.get("NJ_DCA_MAX_RETRIES") or 4),
        )
