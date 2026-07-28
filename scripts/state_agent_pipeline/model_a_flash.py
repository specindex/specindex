"""Model A: Gemini Flash high-recall entity extraction from Socrata rows."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from .config import Settings
from .schemas import CandidateEntity, FlashExtractBatch


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


def _flash_prompt(rows: list[dict[str, Any]]) -> str:
    return f"""You are SpecIndex Model A (high-recall gatherer) for New Jersey DCA construction permits.

INPUT: raw Socrata JSON rows from data.nj.gov dataset w9se-dmra.

TASK: Convert each row into a structured candidate entity. Be OVERLY inclusive.
If municipality/block/lot/permit details might refer to the same property as another
row in this batch, set flagged_uncertain=true and possible_duplicate_of_pk to that pk.
Invent a short project_name_guess and address_guess from available fields (muni + block/lot);
do not invent street addresses that are not implied.

Return ONLY valid JSON:
{{
  "entities": [
    {{
      "source_pk": "...",
      "permit_no": "...",
      "municipality": "...",
      "county": "...",
      "block": "...",
      "lot": "...",
      "use_group": "...",
      "permit_type": "...",
      "permit_date": "YYYY-MM-DD or null",
      "process_date": "YYYY-MM-DD or null",
      "construction_cost_usd": 0,
      "square_feet": 0,
      "project_name_guess": "...",
      "address_guess": "...",
      "flagged_uncertain": false,
      "possible_duplicate_of_pk": null,
      "notes": "short"
    }}
  ]
}}

ROWS:
{json.dumps(rows, indent=2)[:100000]}
"""


def extract_with_flash(rows: list[dict[str, Any]], settings: Settings) -> list[CandidateEntity]:
    if not rows:
        return []
    from google import genai
    from google.genai import types

    # Prefer us-central1 for gemini-2.5-flash; global for 3.x flash.
    location = settings.google_cloud_location
    model = settings.flash_model
    if model.startswith("gemini-2.5") and location == "global":
        location = "us-central1"

    client = genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=location,
    )

    all_entities: list[CandidateEntity] = []
    batch_size = settings.flash_batch_size
    batches = [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]

    for bi, batch in enumerate(batches, 1):
        print(f"[flash] batch {bi}/{len(batches)} ({len(batch)} rows)…", file=sys.stderr)
        text = ""
        last_err: Exception | None = None
        for attempt in range(settings.max_retries):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=_flash_prompt(batch),
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                text = getattr(resp, "text", None) or ""
                if not text and getattr(resp, "candidates", None):
                    parts = []
                    for c in resp.candidates:
                        content = getattr(c, "content", None)
                        for p in getattr(content, "parts", None) or []:
                            t = getattr(p, "text", None)
                            if t:
                                parts.append(t)
                    text = "\n".join(parts)
                break
            except Exception as e:
                last_err = e
                wait = min(60, (2**attempt) * 3)
                print(f"[flash] retry {attempt + 1}: {e}; sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
        else:
            raise RuntimeError(f"Flash failed: {last_err}")

        try:
            blob = _extract_json(text)
            parsed = FlashExtractBatch.model_validate(blob if isinstance(blob, dict) else {"entities": blob})
            raw_by_pk = {str(r.get("pk")): r for r in batch}
            for entity in parsed.entities:
                raw = raw_by_pk.get(entity.source_pk)
                if raw is None:
                    continue
                # permit_no/municipality are identity-critical (drive
                # canonical_golden_id in model_b_sonnet.py, which must
                # match pull-nj-dca.py's id scheme exactly) -- never trust
                # Flash's own transcription of them, only its judgment on
                # the softer fields (project_name_guess, notes, etc.).
                entity.permit_no = str(raw.get("permitno") or "") or None
                muni_raw = (raw.get("muniname") or "").strip()
                entity.municipality = muni_raw.title() if muni_raw else entity.municipality
            all_entities.extend(parsed.entities)
        except Exception as e:
            print(f"[flash] parse/validate error batch {bi}: {e}", file=sys.stderr)
            # Fallback: deterministic mapping so pipeline still advances
            all_entities.extend(_deterministic_entities(batch))
        time.sleep(0.5)

    return all_entities


def _deterministic_entities(rows: list[dict[str, Any]]) -> list[CandidateEntity]:
    out: list[CandidateEntity] = []
    for r in rows:
        pk = str(r.get("pk") or "")
        if not pk:
            continue
        muni = (r.get("muniname") or "").strip()
        try:
            cost = float(r.get("constcost") or 0) or None
        except (TypeError, ValueError):
            cost = None
        try:
            sqft = float(r.get("squarefeet") or 0) or None
        except (TypeError, ValueError):
            sqft = None
        out.append(
            CandidateEntity(
                source_pk=pk,
                permit_no=str(r.get("permitno") or "") or None,
                municipality=muni.title() if muni else None,
                county=(r.get("county") or "").strip().title() or None,
                block=str(r.get("block") or "") or None,
                lot=str(r.get("lot") or "") or None,
                use_group=(r.get("usegroupdesc") or "").strip() or None,
                permit_type=(r.get("permittypedesc") or "").strip() or None,
                permit_date=(str(r.get("permitdate") or "")[:10] or None),
                process_date=(str(r.get("processdate") or "")[:10] or None),
                construction_cost_usd=cost,
                square_feet=sqft,
                project_name_guess=f"{(r.get('permittypedesc') or 'Permit')} - {muni.title()}"[:120],
                address_guess=f"Block {r.get('block')} Lot {r.get('lot')}, {muni.title()}" if r.get("block") else muni.title(),
                flagged_uncertain=True,
                notes="deterministic fallback (Flash parse failed)",
            )
        )
    return out
