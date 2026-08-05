#!/usr/bin/env python3
"""Preflight: check every credential, config value and IAM role this repo needs.

WHY THIS EXISTS. Three separate settings were missing or wrong for weeks and
none of them produced an error -- each degraded into a plausible-looking zero:

  * DOCUMENT_AI_PROCESSOR_ID was never set, though the processor existed and
    was ENABLED. Every scanned page was recorded as "skipped_no_docai": 471
    skipped, 672 stored near-empty. Local agency addenda are frequently scanned
    images, so "no substitution rulings found" was indistinguishable from
    "we could not read the documents that contain them".
  * github-actions-puller had no Cloud Run permissions at all, so the API
    deploy workflow could never have worked regardless of how it was written.
  * claude-cloudsql lacked documentai.apiUser, so OCR returned PERMISSION_DENIED
    from a processor that was running fine.

Every one of those is invisible until something downstream quietly returns
nothing. This makes them visible in ten seconds.

IAM ROLES ARE PART OF THE ENVIRONMENT and do not live in git. Listing them
here, with the exact grant command, is the closest thing to version-controlling
them.

Usage:
  python3 scripts/verify-environment.py
  python3 scripts/verify-environment.py --fix     # print the commands to run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT = "specindex-ai"

# service account -> roles it must hold, and what breaks without each.
REQUIRED_IAM: dict[str, list[tuple[str, str]]] = {
    "github-actions-puller@specindex-ai.iam.gserviceaccount.com": [
        ("roles/run.admin", "API deploy workflow cannot create/update the service"),
        ("roles/iam.serviceAccountUser", "cannot act as the Cloud Run runtime SA"),
        ("roles/cloudbuild.builds.editor", "`gcloud run deploy --source` cannot build"),
        ("roles/artifactregistry.writer", "cannot push the built image"),
        ("roles/cloudsql.client", "workflows cannot reach Cloud SQL"),
    ],
    "claude-cloudsql@specindex-ai.iam.gserviceaccount.com": [
        ("roles/documentai.apiUser", "OCR fails; scanned pages silently stored empty"),
        # apiUser grants PROCESSING but not LISTING. The auto-discovery added to
        # extract-document-text.py calls list_processors, so without viewer the
        # fallback that was meant to remove a config dependency fails instead --
        # caught by this very check on its first run.
        ("roles/documentai.viewer", "processor auto-discovery fails; must pin the id by hand"),
        ("roles/cloudsql.client", "scripts cannot reach the database"),
        ("roles/aiplatform.user", "Gemini calls fail"),
    ],
}

# GitHub Actions secrets, and what silently breaks without them.
REQUIRED_GH_SECRETS = [
    ("WIF_PROVIDER", "all GCP workflows fail to authenticate"),
    ("WIF_SERVICE_ACCOUNT", "all GCP workflows fail to authenticate"),
    ("FIREBASE_SERVICE_ACCOUNT_SPECINDEX_AI", "site deploy fails"),
]


def sh(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return p.returncode, (p.stdout or p.stderr)
    except Exception as e:  # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


def check_env() -> list[tuple[bool, str, str]]:
    out = []
    root = Path(__file__).resolve().parent.parent
    env = {}
    f = root / ".env"
    if f.is_file():
        for line in f.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    for key, why in [
        ("SPECINDEX_DB_PASSWORD", "cannot connect to Cloud SQL"),
        ("SAM_API_KEY", "SAM.gov pulls fail"),
        ("DOCUMENT_AI_PROCESSOR_ID",
         "OCR falls back to auto-discovery; pin it to avoid surprises"),
    ]:
        ok = bool(env.get(key) or os.environ.get(key))
        out.append((ok, f".env {key}", why))
    return out


def check_docai() -> list[tuple[bool, str, str]]:
    """Is there an ENABLED OCR processor, and can we actually call it?"""
    out = []
    try:
        from google.cloud import documentai_v1 as documentai

        c = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": "us-documentai.googleapis.com"})
        procs = [p for p in c.list_processors(parent=f"projects/{PROJECT}/locations/us")
                 if p.type_ == "OCR_PROCESSOR"]
        enabled = [p for p in procs if p.state == documentai.Processor.State.ENABLED]
        out.append((bool(enabled),
                    f"Document AI OCR processor ({len(enabled)} enabled of {len(procs)})",
                    "scanned pages CANNOT be read; addenda are often scanned"))
    except Exception as e:  # noqa: BLE001
        out.append((False, f"Document AI reachable ({type(e).__name__})",
                    "OCR unavailable; scanned pages stored empty"))
    return out


def check_iam() -> list[tuple[bool, str, str]]:
    out = []
    rc, txt = sh(["gcloud", "projects", "get-iam-policy", PROJECT,
                  "--flatten=bindings[].members", "--format=value(bindings.members,bindings.role)"])
    if rc != 0:
        out.append((False, "gcloud IAM readable", "run `gcloud auth login`"))
        return out
    held: dict[str, set[str]] = {}
    for line in txt.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[0].startswith("serviceAccount:"):
            held.setdefault(parts[0].split(":", 1)[1], set()).add(parts[1])
    for sa, roles in REQUIRED_IAM.items():
        for role, why in roles:
            out.append((role in held.get(sa, set()), f"{sa.split('@')[0]} :: {role}", why))
    return out


def check_gh_secrets() -> list[tuple[bool, str, str]]:
    rc, txt = sh(["gh", "secret", "list"])
    if rc != 0:
        return [(False, "gh secrets readable", "install/auth the gh CLI")]
    names = {l.split()[0] for l in txt.splitlines() if l.strip()}
    return [(n in names, f"gh secret {n}", why) for n, why in REQUIRED_GH_SECRETS]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="print the commands that fix failures")
    args = ap.parse_args()

    groups = [("Local config (.env)", check_env()),
              ("Document AI", check_docai()),
              ("IAM roles", check_iam()),
              ("GitHub Actions secrets", check_gh_secrets())]

    failures = []
    for title, rows in groups:
        print(f"\n=== {title} ===")
        for ok, name, why in rows:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            if not ok:
                print(f"        -> {why}")
                failures.append(name)

    print(f"\n{'ALL CHECKS PASS' if not failures else f'{len(failures)} FAILURE(S)'}")

    if failures and args.fix:
        print("\n--- fixes ---")
        for sa, roles in REQUIRED_IAM.items():
            for role, _ in roles:
                if any(f.startswith(sa.split("@")[0]) and role in f for f in failures):
                    print(f"gcloud projects add-iam-policy-binding {PROJECT} \\\n"
                          f'  --member="serviceAccount:{sa}" \\\n'
                          f'  --role="{role}" --condition=None')
        if any("DOCUMENT_AI_PROCESSOR_ID" in f for f in failures):
            print("# pin the OCR processor (auto-discovery works, but pinning is explicit):")
            print("#   echo 'DOCUMENT_AI_PROCESSOR_ID=<id>' >> .env")
            print("# list ids:  python3 scripts/verify-environment.py")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
