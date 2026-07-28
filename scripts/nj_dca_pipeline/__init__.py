#!/usr/bin/env python3
"""NJ DCA Socrata incremental ingestion + Flash gather + Sonnet dedupe.

Architecture:
  Socrata (incremental) -> Model A Gemini Flash (high recall)
                        -> Model B Claude Sonnet (golden-record dedupe)
                        -> local JSON (+ optional merge into data/states/nj.json)

Entry:
  python3 -m scripts.nj_dca_pipeline.main
  python3 scripts/nj_dca_pipeline/main.py --lookback-days 3 --limit 50
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
