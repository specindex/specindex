# Contributing

## Working in parallel without colliding

If more than one person (or more than one Claude Code session) is
working on this repo at the same time, **use a separate git worktree per
person/session** rather than sharing one working directory. A shared
working directory means one session's `git checkout`, `git reset`, or
cherry-pick moves the branch out from under whoever else is running in
that same directory -- the actual GitHub history is never at risk (see
branch protection below), but the *local* working tree can get seriously
confusing.

```bash
# From your main clone, one worktree per person/session:
git worktree add ../specindex-asif main
git worktree add ../specindex-agent2 main

# Each one is a real, independent working directory + checkout --
# branch switches, resets, and cherry-picks in one never touch the other.
git worktree list      # see all active worktrees
git worktree remove ../specindex-agent2   # clean up when done
```

Everyone still pushes to and pulls from the same `origin` -- worktrees
only isolate the *local* checkout, not the remote history.

## Branch protection on `main`

`main` is protected (as of 2026-07-29):

- **No direct pushes.** All changes land via pull request.
- **The `build_and_preview` check must pass** before a PR can merge (this
  is the existing Firebase Hosting PR workflow, which already runs `npm
  run build` on every PR -- nothing new to configure, it's just now
  required rather than advisory).
- **No force-pushes or branch deletion**, enforced even for repo admins.

This is enforced at the GitHub level, so it protects the repo regardless
of what happens in anyone's local working directory.

## The PR flow this repo actually uses

One fix, one branch, one PR:

```bash
git fetch origin main
git branch fix/short-description origin/main
git checkout fix/short-description
# ... make the change, verify it (typecheck, build) ...
git add <specific files>          # not -A -- review what's staged
git commit -m "..."
git push -u origin fix/short-description
gh pr create --title "..." --body "..."
gh pr merge <number> --merge --delete-branch
```

Branching off `origin/main` explicitly (not off whatever the local
`main` happens to point to) keeps a fix isolated from anything else
in-flight locally. Stage specific files, not everything `git status`
shows -- a shared working directory (or a stale worktree) can have other
work sitting uncommitted that isn't yours to bundle into your commit.

## Recovering from a collision

If a shared working directory does end up with someone else's commit
sitting on a branch you need to touch:

```bash
git branch preserve/whatever-it-was <sha>   # tag it so it's not lost
git checkout main
git reset --hard origin/main                # realign to the real source of truth
```

`origin/main` (GitHub) is always the source of truth -- a confusing
local checkout is recoverable as long as nothing is deleted before it's
tagged onto a branch first.
