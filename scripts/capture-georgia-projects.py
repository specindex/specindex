#!/usr/bin/env python3
"""Structure Georgia commercial project research with Kimi (Moonshot).

Requires: MOONSHOT_API_KEY in the environment.
Do not commit API keys.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "georgia-commercial-projects.json"
PUBLIC = ROOT / "public" / "data" / "georgia-commercial-projects.json"
BASE = "https://api.moonshot.ai/v1"


def chat(messages: list[dict], api_key: str) -> dict:
    body = {
        "model": "kimi-k3",
        "messages": messages,
        "max_tokens": 32768,
        "reasoning_effort": "high",
    }
    req = urllib.request.Request(
        f"{BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        print("Set MOONSHOT_API_KEY", file=sys.stderr)
        return 1

    research_path = ROOT / "data" / "research-notes.txt"
    if not research_path.exists():
        print(f"Missing {research_path}", file=sys.stderr)
        return 1

    research = research_path.read_text()
    prompt = f"""Structure SpecIndex Georgia project JSON from research below.
Output JSON only with keys generated_at, geography, capture_method, projects, notes.
{research}
"""
    data = chat(
        [
            {"role": "system", "content": "Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        api_key,
    )
    content = data["choices"][0]["message"].get("content") or ""
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        print("No JSON in model response", file=sys.stderr)
        return 1
    parsed = json.loads(text[start : end + 1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(parsed, indent=2) + "\n"
    OUT.write_text(payload)
    PUBLIC.write_text(payload)
    print(f"Wrote {len(parsed.get('projects', []))} projects to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
