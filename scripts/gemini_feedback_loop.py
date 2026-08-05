#!/usr/bin/env python3
"""Close the loop with Gemini: report verification outcomes back to it.

WHY. Gemini is the designated backup when a source dies or a portal gates, and
it earns that role -- it recovered the VA master specs after the TIL went
Okta-gated. But it mixes real and fabricated answers at equal confidence, and
without feedback it repeats the same class of error every session:

  * VA specs: gave a REAL file path (57 KB .docx) and a FABRICATED index URL
    (soft-404, 1,359 bytes, byte-identical to the baseline) in ONE answer.
  * Top-10 county portals: 0 of 5 claims survived live checking.
  * Earlier: 4 invented EnerGov hostnames (all DNS failures), and 3 of 5
    supplied URLs non-resolving including a dead Fresno ArcGIS endpoint.

Per Asif (2026-08-05): make it a closed loop. Feed the verified outcome back
so the next answer is conditioned on what actually resolved, and so the model
is told plainly that "unknown" is an acceptable answer and a fabricated URL
is not.

This is step 3 of the 11-step process (the feedback loop) applied to the
research tool itself rather than to a jurisdiction.

The verdict ledger is append-only at data/raw/gemini_verification_log.json so
accuracy can be tracked over time rather than re-litigated from memory.

Usage:
  python3 scripts/gemini_feedback_loop.py --record verdicts.json
  python3 scripts/gemini_feedback_loop.py --send        # replay ledger to Gemini
  python3 scripts/gemini_feedback_loop.py --stats
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LEDGER = Path("data/raw/gemini_verification_log.json")


def load() -> list[dict]:
    if LEDGER.is_file():
        try:
            return json.loads(LEDGER.read_text()).get("entries", [])
        except Exception:  # noqa: BLE001
            return []
    return []


def save(entries: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps({"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                  "entries": entries}, indent=2))


def record(entries: list[dict], new: list[dict]) -> list[dict]:
    seen = {(e.get("claim"), e.get("url")) for e in entries}
    for n in new:
        if (n.get("claim"), n.get("url")) not in seen:
            entries.append(n)
    return entries


def build_feedback(entries: list[dict]) -> str:
    """The message sent back. Concrete, per-URL, with the evidence -- a vague
    'you were wrong' teaches nothing and cannot be acted on."""
    wrong = [e for e in entries if not e.get("verified")]
    right = [e for e in entries if e.get("verified")]
    lines = [
        "FEEDBACK ON YOUR EARLIER ANSWERS. Every URL and claim you gave was "
        "checked live against the real host. Results below.",
        "",
        f"CONFIRMED ({len(right)}):",
    ]
    for e in right[:25]:
        lines.append(f"  OK    {e.get('url') or e.get('claim')}  -- {e.get('evidence','')}")
    lines += ["", f"NOT CONFIRMED ({len(wrong)}):"]
    for e in wrong[:25]:
        lines.append(f"  FAIL  {e.get('url') or e.get('claim')}  -- {e.get('evidence','')}")
    lines += [
        "",
        "What went wrong, specifically:",
        "  * Some URLs returned HTTP 200 but were SOFT-404s -- the body was "
        "byte-identical to a nonsense-path baseline on the same host. HTTP 200 "
        "is not evidence a page exists.",
        "  * Some hostnames were constructed by pattern and do not resolve at all.",
        "  * Portal access verdicts (open vs login-required) were asserted "
        "without a basis and were wrong in both directions.",
        "",
        "How to answer me from now on:",
        "  1. Only give a URL you have actually seen in a search result. Never "
        "construct one from a pattern, even an obvious-looking one.",
        "  2. Say \"unknown\" when you do not know. An explicit unknown is a "
        "CORRECT and useful answer here; a plausible fabrication is the single "
        "most costly one, because it is expensive to disprove.",
        "  3. Separate what you SAW from what you INFER, and label which is which.",
        "  4. For access claims (login required / public), state the evidence "
        "you are relying on, or say you could not determine it.",
    ]
    return "\n".join(lines)


def send(msg: str) -> str:
    from state_agent_pipeline.config import Settings  # noqa: PLC0415
    from google import genai  # noqa: PLC0415
    from google.genai import types  # noqa: PLC0415

    s = Settings.from_env()
    c = genai.Client(vertexai=True, project=s.google_cloud_project,
                     location=s.google_cloud_location)
    cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    r = c.models.generate_content(model=s.flash_model, contents=msg, config=cfg)
    return r.text or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=Path, help="json list of {claim,url,verified,evidence}")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    entries = load()
    if args.record:
        entries = record(entries, json.loads(args.record.read_text()))
        save(entries)
        print(f"ledger now holds {len(entries)} verified claims -> {LEDGER}")

    if args.stats or not (args.record or args.send):
        ok = sum(1 for e in entries if e.get("verified"))
        print(f"claims checked : {len(entries)}")
        print(f"  confirmed    : {ok}")
        print(f"  fabricated   : {len(entries) - ok}")
        if entries:
            print(f"  accuracy     : {ok / len(entries) * 100:.0f}%")
        for e in entries:
            if not e.get("verified"):
                print(f"    FAIL {(e.get('url') or e.get('claim'))[:78]}")

    if args.send:
        if not entries:
            print("nothing to send")
            return 0
        msg = build_feedback(entries)
        print("--- sending feedback ---")
        print(send(msg)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
