"""Shared deterministic-hash helper for BaseIngestionProvider implementations."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def hash_fields(row: dict[str, Any], fields: list[str]) -> str:
    """SHA-256 over a fixed, ordered set of field values -- stable across
    runs regardless of the source dict's key ordering. Use for platforms
    with a real composite business key (e.g. NJ: treasurycode+block+lot+
    permitno; ArcGIS: state-specific parcel/permit fields)."""
    parts = [str(row.get(f, "")).strip() for f in fields]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def hash_row(row: dict[str, Any]) -> str:
    """SHA-256 over the entire row, sorted by key for stability. Use only
    when a platform genuinely has no reliable composite key (flat CSV/S3
    downloads with no permit-number-like field) -- this hash changes if
    ANY field value changes, so it's an equality check, not an identity
    check, and will treat a corrected typo as a "new" row."""
    canonical = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
