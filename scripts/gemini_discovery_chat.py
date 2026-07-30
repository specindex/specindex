#!/usr/bin/env python3
"""Durable, resumable Gemini chat session for county-source discovery.

Replaces the earlier scratch-directory version (a /tmp JSON file tied to
one-off Bash invocations, which doesn't survive a session restart).
Session history is stored under data/gemini_sessions/{name}.json
(gitignored -- this is working conversation state, not corpus data) so
the same named session (e.g. "harris_houston", "tx_batch_2") can be
resumed across separate script invocations, keeping Gemini's own
conversational context intact across a multi-step jurisdiction
investigation -- per Asif's explicit ask (2026-07-28): "default use
gemini for search so gemini has the context".

Search grounding is always on -- confirmed live 2026-07-28 that grounded
queries have a meaningfully better real-URL hit rate than bare
generation (Bexar: 6/8 real vs Dallas's earlier 0/7 ungrounded).
Everything Gemini returns still needs independent live verification
(HTTP/Playwright) before being trusted -- this script does not verify
anything itself, it only manages the conversation.

Usage:
    python3 scripts/gemini_discovery_chat.py --session harris_houston "message text"
    python3 scripts/gemini_discovery_chat.py --session harris_houston --reset
    python3 scripts/gemini_discovery_chat.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time as _time
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from state_agent_pipeline.config import Settings  # noqa: E402

SESSIONS_DIR = _SCRIPTS.parent / "data" / "gemini_sessions"

# docs/architecture-2026/01-data-platform.md P2: query-result caching. Keyed
# on (session, normalized message text) ONLY -- not the full conversation
# history -- so this is deliberately narrower than "cache this exchange":
# it catches the real, common case (an identical message re-sent to the
# same session after a crash/retry/duplicate invocation, a genuinely
# redundant grounded search) without pretending to understand whether an
# identical string means the same thing at two different points in a
# conversation's history. TTL, not permanent -- discovery research does go
# stale.
CACHE_DIR = _SCRIPTS.parent / "data" / "gemini_query_cache"
CACHE_TTL_SECONDS = float(os.environ.get("GEMINI_QUERY_CACHE_TTL_DAYS", "7")) * 86400


def _normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _cache_path(session: str, message: str) -> Path:
    key = hashlib.sha256(f"{session}:{_normalize_query(message)}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _cache_get(session: str, message: str) -> str | None:
    path = _cache_path(session, message)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if _time.time() - data["cached_at"] > CACHE_TTL_SECONDS:
        return None
    return data["response"]


def _cache_put(session: str, message: str, response: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(session, message)
    path.write_text(json.dumps({"cached_at": _time.time(), "response": response}))


def _session_path(name: str) -> Path:
    return SESSIONS_DIR / f"{name}.json"


def load_history(name: str) -> list[dict[str, str]]:
    path = _session_path(name)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_turn(name: str, role: str, text: str) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(name)
    history = load_history(name)
    history.append({"role": role, "text": text})
    path.write_text(json.dumps(history, indent=2))


def reset_session(name: str) -> None:
    path = _session_path(name)
    if path.exists():
        path.unlink()


def list_sessions() -> list[str]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(p.stem for p in SESSIONS_DIR.glob("*.json"))


def send(session: str, message: str, max_retries: int = 3) -> str:
    import time

    from google import genai
    from google.genai import types
    from google.auth.exceptions import RefreshError

    cached = _cache_get(session, message)
    if cached is not None:
        print("  [cache hit -- skipping grounded call]", file=sys.stderr)
        save_turn(session, "user", message)
        save_turn(session, "model", cached)
        return cached

    settings = Settings.from_env()
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)

    history = [
        types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])])
        for turn in load_history(session)
    ]
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])
    chat = client.chats.create(model=settings.flash_model, config=config, history=history)

    resp = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = chat.send_message(message)
            break
        except RefreshError:
            # Not transient -- retrying won't fix an expired login. Fail fast
            # with the real fix (run `gcloud auth application-default login`).
            raise
        except Exception as e:  # noqa: BLE001 -- broad on purpose, network/timeout errors vary by transport
            if attempt == max_retries:
                raise
            wait = 2**attempt
            print(f"  [retry {attempt}/{max_retries}] {e} -- waiting {wait}s", file=sys.stderr)
            time.sleep(wait)

    save_turn(session, "user", message)
    save_turn(session, "model", resp.text)
    _cache_put(session, message, resp.text)
    return resp.text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("message", nargs="?", help="Message to send. Reads stdin if omitted.")
    parser.add_argument("--session", default="default", help="Named session to resume/append to (default: 'default')")
    parser.add_argument("--reset", action="store_true", help="Clear the named session's history and exit")
    parser.add_argument("--list", action="store_true", help="List existing session names and exit")
    args = parser.parse_args(argv)

    if args.list:
        sessions = list_sessions()
        print("\n".join(sessions) if sessions else "No sessions yet.")
        return 0

    if args.reset:
        reset_session(args.session)
        print(f"Session {args.session!r} reset.", file=sys.stderr)
        return 0

    message = args.message or sys.stdin.read()
    if not message.strip():
        parser.error("no message provided (pass as argument or via stdin)")

    print(send(args.session, message))
    return 0


if __name__ == "__main__":
    sys.exit(main())
