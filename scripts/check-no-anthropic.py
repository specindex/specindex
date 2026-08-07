#!/usr/bin/env python3
"""Fail if anything in this repo can call Anthropic. Gemini on Vertex only.

Asif's decision 2026-08-07: every model call in this project goes to Google
Gemini via Vertex AI. The trigger was the classifier dying 150-for-150 on "Your
credit balance is too low to access the Anthropic API", but the standing rule is
broader than cost -- one provider, one bill, one place to reason about quota.

BOTH PATHS COUNT. `anthropic.Anthropic()` bills Anthropic directly;
`AnthropicVertex()` bills GCP but still runs Claude. The instruction was Gemini,
not "Anthropic somewhere cheaper", so this rejects both.

A CHECK RATHER THAN A NOTE, for the reason the gitignore guard exists: a note in
CLAUDE.md was written twice this session and the same class of mistake happened
again 20 minutes later. Enforcement belongs in CI.
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Live call paths. Importing the SDK is not itself a call, but it is the only
# way to make one, so it is treated as a finding.
PATTERNS = [
    (re.compile(r"\bimport\s+anthropic\b|\bfrom\s+anthropic\s+import\b"), "imports the anthropic SDK"),
    (re.compile(r"anthropic\.Anthropic\s*\("), "calls Anthropic directly"),
    (re.compile(r"\bAnthropicVertex\s*\("), "calls Claude via Vertex (still not Gemini)"),
    (re.compile(r"api\.anthropic\.com"), "hits the Anthropic endpoint"),
    (re.compile(r"ANTHROPIC_API_KEY"), "wires the Anthropic key"),
]

# worktrees/ holds full repo COPIES from old agent runs -- scanning them
# multiplied every real finding by ~250 and buried the ten that matter. They are
# checkouts, not source; fixing the source fixes them.
SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", ".venv", "worktrees"}
# This file names the patterns it forbids; excluding it is not an exemption for
# anything else.
SELF = "scripts/check-no-anthropic.py"


def main() -> int:
    hits: list[tuple[str, int, str]] = []
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(d in p.parts for d in SKIP_DIRS):
            continue
        if p.suffix not in (".py", ".ts", ".tsx", ".js", ".yml", ".yaml", ".txt", ".sh"):
            continue
        rel = str(p.relative_to(ROOT))
        if rel == SELF:
            continue
        try:
            text = p.read_text(errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for pat, why in PATTERNS:
                if pat.search(line):
                    hits.append((rel, n, why))
                    break

    if not hits:
        print("OK: no Anthropic call path in the repo. Gemini on Vertex only.")
        return 0

    print("ANTHROPIC CALL PATH FOUND -- this project uses Gemini on Vertex only:\n")
    for rel, n, why in sorted(set(hits)):
        print(f"  {rel}:{n}\n      {why}")
    print(f"\n{len(set(hits))} occurrence(s). Route the call through "
          f"google.genai with vertexai=True, or delete the dead script.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
