# Arkansas Spec Pull — RERUN (2026-08-06, v2.1 skill)

Smoke test after installing the v2.1 handoff. Diffed against
`coverage/test-results/arkansas/summary.md` (the packaged baseline).

## Funnel: rerun vs baseline

| Metric | Baseline | Rerun | Verdict |
|---|---|---|---|
| Projects found | 8 (1 Vert + 7 DOT) | **7 (0 Vert + 7 DOT)** | DOT identical; vertical source now blocked |
| Projects with any documents | 8 / 8 (100%) | **7 / 7 (100%)** | same |
| Confirmed spec docs | 7 / 8 (87.5%) | **7 / 7 (100%)** | **same 7 documents** |
| Recovered by stage 4 | 0 / 1 attempted | n/a (no gap to fill) | — |

**The DOT half reproduces exactly: 7 projects, 7 with documents, 7 content-verified.**
Same portal, same counts. Healthy.

The percentage moved 87.5% → 100% only because the single vertical project that
had no spec book is now absent from the denominator. That is a coverage loss
presenting as a metric improvement, which is exactly the shape a funnel number
can hide — the rerun found *fewer* documents, not more.

## The one real difference: sas.arkansas.gov is now host-wide 403

| Probe | Result |
|---|---|
| `/building-authority/bid-announcements/` | **403, 548 bytes** |
| `/` (site root) | **403, 548 bytes** |
| `/robots.txt` | **200** — `Disallow:` (empty, allows all), `Crawl-delay: 10` |

The host is up and its own robots.txt permits crawling; an edge/WAF layer is
rejecting HTML requests. Browser User-Agent and Referer were sent — permitted
under v2.1 rule 2 — and the block persists. An independent adapter run earlier
today hit the same wall from a different code path, including real headless
Chromium, so this is not a client artefact.

Rule 2 forbids IP rotation to evade a block, so the correct action is to log it
and stop. Status: `dead link` at the document level, block at the host level.
Not a portal migration — the URL is right, the host is refusing.

## Status of the two sources

| Source | Type | Tier | Status |
|---|---|---|---|
| ARDOT Currently Advertised Projects | DOT | 1 | **healthy** — 7 projects, 7 spec docs verified |
| DBA Bid Announcements (sas.arkansas.gov) | Vertical | 1 | **blocked** — host-wide 403, revisit; do not evade |

Spec content confirmed by reading the documents, not by status code: ARDOT
proposals carry SS/SP section numbering plus measurement/payment headings and
FHWA-1273, per skill rule 6.
