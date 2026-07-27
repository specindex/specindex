"""Abstract Ingestion Provider interface.

Node 1 of the per-state pipeline (Deterministic Ingestor) is a Strategy
Pattern: each state's open-data portal technology (Socrata, ArcGIS REST,
CKAN, or a flat CSV/S3 download) gets its own concrete provider, but every
provider exposes the same two operations so the downstream nodes (Flash
extraction, Sonnet dedupe, persistence) never need to know which platform
a given state uses.

Two responsibilities per provider, matching the two real problems every
incremental state pipeline has to solve regardless of platform:

1. fetch_delta(last_watermark) -- pull only rows new since the last
   successful run. What "watermark" means is platform- (and often
   dataset-) specific: a monotonic recordid for Socrata, an OBJECTID
   floor for ArcGIS, an internal CKAN _id, or a file's Last-Modified
   header / a full-row hash for flat downloads that have no reliable
   incrementing key at all.

2. compute_deterministic_hash(row) -- a stable, source-agnostic identity
   for a raw row, used both for within-run dedup (the same row appearing
   twice in one paginated pull) and as an idempotency key across runs
   (so re-processing a row that was already loaded is a no-op, not a
   duplicate). This is deliberately NOT the same thing as Node 3's
   semantic/fuzzy dedup (Sonnet) -- this hash only says "this exact raw
   record has been seen before," not "this record describes the same
   real-world project as some other record."
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseIngestionProvider(ABC):
    """One concrete subclass per open-data platform (Socrata/ArcGIS/CKAN/
    CSV). State agents don't instantiate these directly -- see
    core/ingestion/factory.py's IngestionFactory, which picks the right
    provider from a state's `provider_type` config field."""

    @abstractmethod
    def fetch_delta(self, last_watermark: str) -> list[dict[str, Any]]:
        """Return raw rows newer than `last_watermark`. An empty/"0"
        watermark means "first run" -- providers should apply a bounded
        lookback (never a full unbounded table scan; NJ's DCA dataset
        alone is 2.75M rows) rather than pulling everything."""
        raise NotImplementedError

    @abstractmethod
    def compute_deterministic_hash(self, row: dict[str, Any]) -> str:
        """Stable identity for a raw row -- SHA-256 hex digest by
        convention (see hashing.py), computed over whichever fields this
        provider's dataset actually has as a real business/composite key,
        falling back to a whole-row hash when no such key exists (flat
        CSV/S3 sources)."""
        raise NotImplementedError

    @abstractmethod
    def next_watermark(self, rows: list[dict[str, Any]], current: str) -> str:
        """Given the rows just fetched, return the watermark value the
        *next* run should use. Kept as a provider method (not generic
        max()-of-a-field logic in the runner) because what "advance" means
        differs by platform: Socrata advances on a numeric recordid,
        ArcGIS on OBJECTID, CKAN on its internal _id, flat-file providers
        often have no field to advance at all and instead track a
        content hash set or a source Last-Modified timestamp."""
        raise NotImplementedError
