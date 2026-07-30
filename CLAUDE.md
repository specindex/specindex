# Cost-optimization guardrails

- **Targeted file scoping**: only inspect/edit files explicitly named in the prompt or their direct dependencies. No repo-wide `find`/`grep` sweeps unless asked.
- **Concise output**: no full-file reprints — output diffs or the modified function only. Keep reasoning brief on standard edits/bug fixes.
- **Proactive compacting**: when context reaches ~70% or a sub-task completes, summarize progress, drop intermediate debug logs, and compact rather than carrying it forward. At 15 user messages in a session, flag that `/compact` or `/clear` is worth running.
