"""Model B: Claude Sonnet (or Gemini Pro) golden-record dedupe."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from project_identity import slugify  # noqa: E402

from .config import Settings
from .schemas import CandidateEntity, GoldenRecord, SonnetDedupeBatch


def canonical_golden_id(
    municipality: str | None, permit_numbers: list[str], block: str | None, lot: str | None
) -> str:
    """Deterministic id, computed in code -- never trust the LLM's own
    golden_id string. Must match pull-nj-dca.py's scheme
    (nj-dca-{slugify(muni-permit_no)}) when a permit number is known, so
    the deterministic puller and this pipeline resolve to the SAME id for
    the same real-world permit instead of silently double-counting it
    (same_project() in project_identity.py treats two different
    nj-dca-* ids as different projects by design -- it will never catch
    this collision for you).
    """
    muni = (municipality or "unknown").strip()
    permit_no = permit_numbers[0] if permit_numbers else None
    key = f"{muni}-{permit_no}" if permit_no else f"{muni}-{block or ''}-{lot or ''}"
    return f"nj-dca-{slugify(key)}"[:80]


def _extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        import re

        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re

        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            raise
        return json.loads(m.group(1))


def _sonnet_prompt(entities: list[dict[str, Any]]) -> str:
    return f"""You are SpecIndex Model B (high-precision deduplicator / consolidator).

Model A (Gemini Flash) produced a high-recall candidate list from NJ DCA permits.
Flash did NOT deduplicate. You see the FULL candidate set for this batch.

TASK - entity resolution / golden records:
1. Identify candidates that are the SAME permit or SAME property project
   (same municipality + block/lot, or same permit_no, or clear fuzzy matches).
2. Merge each group into one golden record; preserve non-conflicting metadata
   (union permit numbers, sum costs only when clearly additive alterations on
   the same open project; otherwise keep the max cost and note the choice).
3. Resolve location ambiguities (normalize municipality/county casing; keep block/lot).
4. Drop empty/junk candidates.

Return ONLY valid JSON:
{{
  "records": [
    {{
      "golden_id": "nj-dca-...",
      "source_pks": ["..."],
      "permit_numbers": ["..."],
      "municipality": "...",
      "county": "...",
      "block": "...",
      "lot": "...",
      "use_group": "...",
      "permit_types": ["..."],
      "earliest_permit_date": "YYYY-MM-DD",
      "latest_process_date": "YYYY-MM-DD",
      "construction_cost_usd": 0,
      "square_feet": 0,
      "project_name": "...",
      "address": "...",
      "doc_type": "permit",
      "merge_reason": "same block/lot",
      "confidence": 0.9
    }}
  ],
  "dropped_pks": [],
  "merged_groups": 0
}}

CANDIDATES:
{json.dumps(entities, indent=2)[:120000]}
"""


def dedupe_with_sonnet(entities: list[CandidateEntity], settings: Settings) -> list[GoldenRecord]:
    if not entities:
        return []
    payload = [e.model_dump() for e in entities]
    batches = [
        payload[i : i + settings.sonnet_batch_size]
        for i in range(0, len(payload), settings.sonnet_batch_size)
    ]
    all_records: list[GoldenRecord] = []

    for bi, batch in enumerate(batches, 1):
        print(
            f"[sonnet/{settings.sonnet_backend}] batch {bi}/{len(batches)} ({len(batch)} candidates)…",
            file=sys.stderr,
        )
        text = _call_model_b(batch, settings)
        try:
            blob = _extract_json(text)
            parsed = SonnetDedupeBatch.model_validate(
                blob if isinstance(blob, dict) else {"records": blob}
            )
            for r in parsed.records:
                r.golden_id = canonical_golden_id(r.municipality, r.permit_numbers, r.block, r.lot)
            all_records.extend(parsed.records)
            print(
                f"[sonnet] batch {bi}: {len(parsed.records)} golden, "
                f"merged_groups={parsed.merged_groups}, dropped={len(parsed.dropped_pks)}",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"[sonnet] parse/validate error batch {bi}: {e}", file=sys.stderr)
            all_records.extend(_passthrough_golden(batch))
        time.sleep(0.5)

    return all_records


def _call_model_b(batch: list[dict[str, Any]], settings: Settings) -> str:
    prompt = _sonnet_prompt(batch)
    last_err: Exception | None = None
    for attempt in range(settings.max_retries):
        try:
            if settings.sonnet_backend == "gemini_pro":
                return _call_gemini_pro(prompt, settings)
            if settings.sonnet_backend == "vertex":
                return _call_claude_vertex(prompt, settings)
            return _call_claude_anthropic(prompt, settings)
        except Exception as e:
            last_err = e
            wait = min(60, (2**attempt) * 4)
            print(f"[sonnet] retry {attempt + 1}: {e}; sleep {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Model B failed: {last_err}")


def _call_claude_anthropic(prompt: str, settings: Settings) -> str:
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY required for sonnet_backend=anthropic")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.sonnet_model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", None) == "text")


def _call_claude_vertex(prompt: str, settings: Settings) -> str:
    from anthropic import AnthropicVertex

    loc = __import__("os").environ.get("VERTEX_CLAUDE_LOCATION") or "global"
    client = AnthropicVertex(project_id=settings.google_cloud_project, region=loc)
    msg = client.messages.create(
        model=settings.sonnet_model,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(getattr(b, "text", "") for b in msg.content)


def _call_gemini_pro(prompt: str, settings: Settings) -> str:
    from google import genai
    from google.genai import types

    location = settings.google_cloud_location
    if settings.sonnet_model.startswith("gemini-2.5") and location == "global":
        location = "us-central1"
    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=location,
    )
    resp = client.models.generate_content(
        model=settings.sonnet_model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.1),
    )
    return getattr(resp, "text", None) or ""


def _passthrough_golden(batch: list[dict[str, Any]]) -> list[GoldenRecord]:
    records: list[GoldenRecord] = []
    for e in batch:
        pk = e.get("source_pk") or "unknown"
        permit_numbers = [e["permit_no"]] if e.get("permit_no") else []
        records.append(
            GoldenRecord(
                golden_id=canonical_golden_id(
                    e.get("municipality"), permit_numbers, e.get("block"), e.get("lot")
                ),
                source_pks=[pk],
                permit_numbers=permit_numbers,
                municipality=e.get("municipality"),
                county=e.get("county"),
                block=e.get("block"),
                lot=e.get("lot"),
                use_group=e.get("use_group"),
                permit_types=[e["permit_type"]] if e.get("permit_type") else [],
                earliest_permit_date=e.get("permit_date"),
                latest_process_date=e.get("process_date"),
                construction_cost_usd=e.get("construction_cost_usd"),
                square_feet=e.get("square_feet"),
                project_name=e.get("project_name_guess"),
                address=e.get("address_guess"),
                merge_reason="passthrough (Model B parse failed)",
                confidence=0.3,
            )
        )
    return records
