# Strategy version history

`docs/SPECINDEX_STRATEGY.md` always holds the **current** strategy. This folder
holds dated snapshots of each version it has had, so a change in thinking can be
read against what it replaced rather than reconstructed from a diff.

Git already records every edit. The reason to keep explicit dated copies anyway:
the strategy is mirrored from a Google Doc that is edited outside this repo, so
the git history records *when we re-mirrored*, not *when the thinking changed*.
A dated file is the honest record of what the strategy actually was on that day.

| Snapshot | Status | What changed |
|---|---|---|
| `SPECINDEX_STRATEGY_2026-08-04_superseded.md` | superseded | Research-heavy version. Moat = **the addenda ledger + the citation graph**. Did not name a competitor in the spec-position space. |
| `SPECINDEX_STRATEGY_2026-08-05.md` | **current** | Moat redefined as **specs plus CRM** — "either half alone is beatable... together they compound." Names **Acelab** (~$25M raised) as the closest competitor. |

## The one change that matters so far

The 08-04 version treated the tracked-project CRM as a later feature and the
ledger as the whole moat. The 08-05 version makes the CRM **half** of it: spec
data gets an agency to *open* the product, and the tracked project record
carrying that agency's own notes is why they do not *leave*. Switching cost
stops being a subscription and becomes institutional memory.

That did not demote the ledger. The ledger remains the only **unique** asset on
the spec side and the only item on the roadmap with a clock on it — addenda come
down after award, so an 18-month archive cannot be built later by anyone who
starts later. "The crawler starts in week one" survived the rewrite unchanged.

## Re-mirroring

When the Doc is edited:

1. Copy the current `SPECINDEX_STRATEGY.md` to a dated file here **before** overwriting it.
2. Re-mirror the Doc into `docs/SPECINDEX_STRATEGY.md`.
3. Add a row above saying what actually changed — not "updated", but which claim
   was replaced by which. A row that says "updated" is worth nothing later.

⚠️ **Appendix I is marked internal in the Doc.** It is retained in these
snapshots because this repo is private and the record should be complete, but it
must be removed from any copy that circulates externally.
