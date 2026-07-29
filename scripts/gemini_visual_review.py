#!/usr/bin/env python3
"""One-off: send a screenshot to Gemini for a multimodal design critique.

Ad hoc companion to gemini_discovery_chat.py -- that script is text-only
(search-grounded chat for fact discovery). This one sends an image, for
cases like "does this page's visual design actually work" where a second
model opinion on the rendered output is more useful than a text
description of it. Not wired into any pipeline; run manually.

Usage:
    python3 scripts/gemini_visual_review.py path/to/screenshot.png "prompt text"
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from state_agent_pipeline.config import Settings  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: gemini_visual_review.py <image_path> <prompt>", file=sys.stderr)
        return 1

    image_path = Path(sys.argv[1])
    prompt = sys.argv[2]

    from google import genai
    from google.genai import types

    settings = Settings.from_env()
    client = genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)

    image_bytes = image_path.read_bytes()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

    resp = client.models.generate_content(
        model=settings.flash_model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part(text=prompt),
                    types.Part(inline_data=types.Blob(mime_type=mime, data=image_bytes)),
                ],
            )
        ],
    )
    print(resp.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
