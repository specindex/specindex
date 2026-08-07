# Portal adapter contract

Every state-portal adapter must satisfy this file. It is enforced by
`scripts/check-portal-adapters.py`, which is the authority — an adapter is done
when the checker passes, **not when an agent reports it done**.

That distinction is the whole point. On 2026-08-06 three separate tasks produced
a confident zero rather than an error: a stale-year filter that discarded a
1,610-page spec book, an address backfill that matched nothing because it used
the wrong NYC dataset, and a portal probe that recorded Delaware as dead when the
host was WAF-blocking plain fetches at HTTP 200. None of those raised an
exception. All would have passed a self-report.

## The five rules

**1. Content-check, never status-check.**
A government host returns HTTP 200 with a landing page, a WAF rejection, or a
login wall. Acceptance requires the PDF magic number `%PDF` **and** a body that
differs from the host's own known-nonsense response. Delaware returns 245 bytes
of `Request Rejected` at status 200.

**2. Try real browser headers before declaring a source dead.**
`User-Agent` of a real browser plus a `Referer` from the portal's own listing
page. Delaware goes from 245 bytes to 9,345,738 bytes on that change alone. Use
Playwright only when the LISTING is JavaScript-rendered; it does not help against
an edge block.

**3. Rate-limit, always.**
Minimum 1.0s between requests to one host. A ban is permanent loss of a source,
and these are the only free sources of this document class.

**4. Emit progress with rate and ETA.**
Any loop over ~30s prints `[n/total] ... x/min ETA`. A silent adapter is
indistinguishable from a hung one — a DOT run burned 1h55m with 7.68s of CPU
before anyone noticed.

**5. Assert the next step can see the output.**
Finish by reading back what was written. A capture that succeeds into a place
nothing reads from is indistinguishable from one that never ran; that shape once
left 78% of captured documents invisible downstream.

**6. Enumerate EVERY document on the listing row, and stamp what each one is.**
`doc_urls` returns all of them — specification, addenda, drawings, legal ad,
notice to contractors, bid tabulation — never just the spec book. Maine's adapter
did this correctly and five of six documents were still lost, because the
*runner* stopped at the first confirmed document to satisfy a "% with ≥1
document" metric.

Each document's type is decided from its **filename** at capture time and stored
in `doc_type`. Downstream code must not re-derive it from `title`: the portal
loader sets title to the project NUMBER ("3820"), so `classify()` returns `other`
and the spec book — the most valuable document on the project — is silently
skipped by extraction.

## Required interface

```python
PORTAL = {
    "state": "Missouri",
    "type": "Vertical",          # Vertical | DOT
    "tier": 1,
    "agency": "...",
    "listing_url": "https://oa.mo.gov/facilities/bid-opportunities",
    "needs_browser": False,      # True only if the LISTING needs JS
    "needs_headers": False,      # True if the host WAF-blocks plain fetches
}

def discover(limit: int = 50) -> list[dict]:
    """Return [{project_name, project_number, bid_date, doc_urls: [...]}].
    Must not download the PDFs -- discovery only.

    doc_urls is EVERY document link on the row, not the spec book alone."""

def fetch(url: str) -> bytes | None:
    """Return PDF bytes, or None. Must content-check before returning."""
```

## Definition of done

An adapter is done when `check-portal-adapters.py` reports **PASS**, which
requires it to have downloaded **at least one real PDF containing CSI division
structure** from that portal. Not a resolving URL. Not a listing page. A spec
document, proven by its own content.

**PASS is necessary, not sufficient — it is a single-document test.** An adapter
that enumerates only the spec book and drops the addenda passes it. Before
calling a portal done, open one listing row in a browser, count the document
links, and compare against `len(doc_urls)`. Maine 3820 posts six; a checker
looking for one CSI-structured PDF would have been satisfied by one of them.

Report failures as failures. "This portal requires a login" is a useful, correct
result. A fabricated success costs a day to discover.
