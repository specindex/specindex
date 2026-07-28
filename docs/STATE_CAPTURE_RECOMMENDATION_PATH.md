# 50-state capture recommendation path

## Cost decision (do not reverse)

Do **not** run Gemini Flash vs Sonnet dual scrapes for all 50 states. The NJ A/B already answered that:

| Job | Winner | Use |
|---|---|---|
| Named commercial web research | Sonnet | Cap to high-value gaps only |
| Public bid/spec PDF retrieval | Sonnet (NJSDA-style boards) | After deterministic project IDs exist |
| Complementary EDA/EIS packets | Gemini Flash (Vertex) | Second pass only |
| Bulk project discovery | Neither LLM | Deterministic APIs |

Repeating the A/B x50 would burn tokens, hit Vertex 429s, and still lose to Socrata/ArcGIS on volume (NJ DCA alone: 53k+).

## Universal pipeline (every state)

```
1. National always-on (token cost: none)
   - scripts/pull-sam-gov-bulk-national.py --states XX
   - scripts/pull-usaspending-bulk-national.py (when wired per-state)

2. Tier 0 statewide register (none)
   - DRI / Act 250 / statewide Socrata / state EDA project DB

3. Tier 1 municipal/county ArcGIS or Socrata (none)
   - Live-verify endpoint before writing pull_*()

4. Tier 2 Accela/EnerGov (none, but ops-heavy)
   - Only major metros; rate-limit carefully

5. Tier 3 targeted web scraper (low)
   - Known bid boards, EDA press RSS, NJSDA-style PDF indexes
   - Deterministic HTML/PDF link harvest, not LLM

6. Tier 4 LLM enrichment (medium, capped)
   - Sonnet: named mega-projects missing owner/architect/docs
   - Gemini Flash: optional second doc pass
   - Hard cap: N projects/month, never full-state discovery
```

## Gold example: New Jersey

1. **Socrata NJDCA** `pull-nj-dca.py` (built) — commercial usegroup allowlist
2. Skip known traps (Newark Ontario ArcGIS, empty JC/Middlesex portals)
3. **Web scraper** for NJEDA awards + NJSDA bid PDFs (deterministic)
4. **Sonnet enrichment** only for named pharma/data-center/hospital rows needing docs
5. Merge → national corpus → build

## Build priority (after batch merge)

Priority = sales territory importance × readiness of a verified Tier 0/1 source.

P0 (script exists or verified, refresh/extend): GA, NJ, NC, NY, IL, FL (Miami-Dade), WA (Seattle), PA (Philly), MD (Montgomery), WI (Milwaukee), VA (Fairfax), MI (Detroit)

P1 (verified live, not built): TX Fort Worth, AZ Maricopa, TN Nashville, CO Denver, Durham NC (if not in NC script)

P2 (research then live-verify one metro): CA, OH, MA, TX Houston/Dallas/Austin

P3 (SAM + light scraper only until a Tier 0 appears): remaining baseline states

## Outputs from regional agents

`data/raw/state-path-recommendations/batch-XX-*.json` → merge to
`data/raw/state-path-recommendations/all-50.json`

Agents read playbooks only. They do not call Anthropic/Vertex for scrapes.
