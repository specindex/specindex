#!/usr/bin/env python3
"""Assert that every path we intend to version is actually committable.

WHY THIS IS A SCRIPT AND NOT A NOTE. The same class of .gitignore rule silently
swallowed new content THREE times across two sessions:

  * `/coverage`  (Jest output) ate coverage/docs and coverage/data
  * `.claude/`   (agent caches) ate .claude/skills, so a skill could never ship
  * `/coverage/*` again -- the negations covered docs/ and data/ but not
    test-results/, added 20 minutes after the first fix

A note went into CLAUDE.md after the second. The third happened anyway. Notes
depend on someone remembering at the moment of the commit, and that is precisely
what keeps failing.

THE FAILURE MODE. `git add <ignored path>` adds nothing, then `git commit`
succeeds with an empty diff. No error, no warning, and the result is
indistinguishable from a clean commit -- while the file exists for nobody but
you. Same shape as a branch pushed with no PR, or a workflow that never fires.

SCOPE, STATED PLAINLY. This catches UNTRACKED files only. Git ignores
.gitignore for a file that is already tracked, so removing a negation for
content that is already committed changes nothing and this check stays green --
verified by doing exactly that. That is not a gap in practice: every one of the
three incidents was NEW content arriving in a directory an old rule already
covered, which is precisely what this sees. But it means the check protects the
next drop, not the last one.

WHY A MANIFEST, NOT A HEURISTIC. The first version of this script flagged
anything ignored that sat beside a tracked file. It returned 336 hits -- .env,
.DS_Store, data/pipeline/*.json -- all correctly ignored. A check that cries
wolf gets switched off, which is worse than no check. So the rule is inverted:
name the paths that MUST be versioned, and fail if any of them is unreachable.
Adding a path here is a deliberate act, and the list is the documentation.
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

# Paths whose contents must always be committable. Extend deliberately.
PROTECTED = [
    ".claude/skills",        # a skill nobody can commit is a skill nobody else has
    ".claude/settings.json", # hooks + permissions; `.claude/*` swallowed it once
    "coverage/docs",         # coverage plan
    "coverage/data",         # verified source tables
    "coverage/test-results", # pipeline evidence -- the diff baseline
    "coverage/pull-log",     # append-only run logs; missed on the 4th collision
    "scripts",
    "db/migrations",
    "docs",
    "api",
    "components",
    "lib",
]


def ignored_under(path: str) -> list[tuple[str, str]]:
    """Files present on disk under `path` that git is ignoring."""
    if not Path(path).exists():
        return []
    out = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", path],
        capture_output=True, text=True).stdout
    hits = []
    for f in (l for l in out.splitlines() if l.strip()):
        # Editor/OS noise is never the point of this check.
        if Path(f).name in (".DS_Store", "Thumbs.db") or f.endswith((".pyc", ".log")):
            continue
        rule = subprocess.run(["git", "check-ignore", "-v", f],
                              capture_output=True, text=True).stdout.strip()
        hits.append((f, rule.split("\t")[0] if rule else "?"))
    return hits


def main() -> int:
    all_hits: list[tuple[str, str]] = []
    for p in PROTECTED:
        all_hits.extend(ignored_under(p))

    if not all_hits:
        print(f"OK: all {len(PROTECTED)} protected paths are committable.")
        return 0

    print("GITIGNORE COLLISION -- these exist on disk but WILL NOT COMMIT:\n")
    for f, rule in sorted(set(all_hits))[:40]:
        print(f"  {f}\n      ignored by {rule}")
    extra = len(set(all_hits)) - 40
    if extra > 0:
        print(f"  ... and {extra} more")
    print("\nAdd a negation to .gitignore, then re-run. Until then `git add` on")
    print("these adds NOTHING and `git commit` succeeds with an empty diff.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
