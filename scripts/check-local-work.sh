#!/usr/bin/env bash
# Report local work that CI cannot see.
#
# WHY THIS EXISTS. `branch-hygiene.yml` answers "is there unmerged work?" for
# anything that reached the remote. Three incidents never got that far:
#
#   - a script was written, run, and swept away by `git stash -u` before it was
#     ever committed;
#   - `git add` on a gitignored path adds nothing and commits clean, so four
#     directories' worth of content never existed for any other machine;
#   - commits sat on a local branch that was never pushed.
#
# None of those are visible to a workflow, by construction. This runs on Stop,
# which is the moment the work is most likely to be abandoned.
#
# It NEVER blocks and never exits non-zero -- a guard that interrupts gets
# switched off, and the point is to be survivable enough to stay on.

set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

warnings=""

# 1. Uncommitted changes. Tracked modifications and untracked files both count:
#    the stash incident was untracked, and stash takes tracked changes too.
dirty="$(git status --porcelain 2>/dev/null | awk 'NR<=10')"
if [ -n "$dirty" ]; then
  n="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  warnings+="${n} uncommitted change(s):"$'\n'"${dirty}"$'\n'
fi

# 2. Unpushed commits, or no upstream at all. A branch with no upstream is the
#    worse case -- it is invisible to `gh pr list` AND to branch-hygiene, which
#    only ever looks at refs that reached the remote.
branch="$(git branch --show-current 2>/dev/null)"
if [ -n "$branch" ]; then
  if upstream="$(git rev-parse --abbrev-ref "@{u}" 2>/dev/null)"; then
    ahead="$(git rev-list --count "${upstream}..HEAD" 2>/dev/null || echo 0)"
    [ "${ahead:-0}" -gt 0 ] && \
      warnings+="${ahead} commit(s) on '${branch}' not pushed to ${upstream}"$'\n'
  else
    has_commits="$(git log --oneline -1 2>/dev/null)"
    [ -n "$has_commits" ] && \
      warnings+="branch '${branch}' has NO upstream -- nothing on the remote knows it exists"$'\n'
  fi
fi

# 3. Gitignore collisions. Reuses the existing guard rather than restating its
#    PROTECTED list, so a new content directory is declared in exactly one file.
if [ -x "$repo/scripts/check-gitignore-collisions.py" ] || \
   [ -f "$repo/scripts/check-gitignore-collisions.py" ]; then
  if ! collisions="$(python3 "$repo/scripts/check-gitignore-collisions.py" 2>&1)"; then
    warnings+="gitignore collision -- files on disk that will NOT commit:"$'\n'
    warnings+="$(echo "$collisions" | awk 'NR<=10')"$'\n'
  fi
fi

[ -z "$warnings" ] && exit 0

python3 -c '
import json, sys
print(json.dumps({"systemMessage": "Local work not on the remote:\n\n" + sys.stdin.read().rstrip()}))
' <<< "$warnings"

exit 0
