"""GCS access, one implementation.

Prefer the service-account key over user ADC. User ADC EXPIRES, and the
failure mode is the dangerous kind: every tenant reports 0 uploads while
happily finding attachments, which reads as "this source has no documents"
rather than as an auth error. A service-account key does not expire.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BUCKET = "specindex-ai-raw-documents"
PROJECT = "specindex-ai"
DEFAULT_KEY = Path.home() / ".config" / "gcloud" / "claude-cloudsql-key.json"


def bucket(name: str = BUCKET):
    from google.cloud import storage  # noqa: PLC0415

    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or (
        str(DEFAULT_KEY) if DEFAULT_KEY.is_file() else None)
    if key and Path(key).is_file():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key
        try:
            b = storage.Client(project=PROJECT).bucket(name)
            # Object-level probe, NOT bucket.exists(): that needs
            # storage.buckets.get, which this SA deliberately lacks, and would
            # make a perfectly usable key look broken.
            b.blob("_healthcheck/probe.txt").exists()
            print(f"[gcs] service-account key {Path(key).name}", file=sys.stderr)
            return b
        except Exception as e:  # noqa: BLE001
            print(f"[gcs] SA key unusable ({type(e).__name__}); falling back to ADC",
                  file=sys.stderr)
            os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    print("[gcs] using user ADC (expires -- prefer the SA key)", file=sys.stderr)
    return storage.Client(project=PROJECT).bucket(name)
