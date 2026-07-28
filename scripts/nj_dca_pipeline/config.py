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
    sonnet_backend: str  # anthropic | vertex | gemini_pro
    sonnet_model: str
    anthropic_api_key: str | None
    socrata_app_token: str | None
    flash_batch_size: int = 40
    sonnet_batch_size: int = 60
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
            or "gemini-2.5-flash",
            sonnet_backend=backend,
            sonnet_model=sonnet_model,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            socrata_app_token=os.environ.get("SOCRATA_APP_TOKEN"),
            flash_batch_size=int(os.environ.get("NJ_DCA_FLASH_BATCH") or 40),
            sonnet_batch_size=int(os.environ.get("NJ_DCA_SONNET_BATCH") or 60),
            max_retries=int(os.environ.get("NJ_DCA_MAX_RETRIES") or 4),
        )
