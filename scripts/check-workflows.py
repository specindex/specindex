#!/usr/bin/env python3
"""Reject workflow files GitHub Actions would refuse to start.

WHY THIS EXISTS. On 2026-08-05 a step in firebase-hosting-pull-request.yml
acquired TWO `env:` keys -- one for a build flag, one for the Firebase secrets.
GitHub Actions will not start a run with a duplicate key, so every build on
that branch finished as a startup failure with ZERO jobs, five times in a row,
and PR #126 sat unmerged for a day.

Two properties of that bug are the reason this script exists rather than a
habit:

  * IT PASSES yaml.safe_load(). PyYAML silently keeps the LAST duplicate key
    instead of raising, so local validation reported a perfectly valid workflow
    with six steps. Validating with a loader that tolerates duplicates cannot
    catch the one error that stops the workflow from starting.
  * IT DOES NOT LOOK LIKE A FAILURE. A run with no jobs reports NO CHECKS
    rather than a failing check, so `gh pr checks` printed "no checks reported"
    and the PR showed BLOCKED with nothing obviously wrong. The signal for
    "this is broken" and the signal for "this hasn't run yet" are identical.

So: strict parse, plus the structural assertions that a startup failure would
otherwise deliver silently and late.

Usage:
  python3 scripts/check-workflows.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that RAISES on a duplicate key instead of keeping the last."""


def _no_duplicate_keys(loader, node, deep=False):
    seen: set = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise ValueError(f"duplicate key {key!r} at line {key_node.start_mark.line + 1}")
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys
)


def check(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        doc = yaml.load(path.read_text(), StrictLoader)
    except Exception as e:  # noqa: BLE001 -- any parse failure is a real failure
        return [f"will not parse: {e}"]

    if not isinstance(doc, dict):
        return ["top level is not a mapping"]

    # `on:` is the YAML 1.1 boolean True once parsed, which is a genuine
    # footgun when reading these files programmatically -- accept either.
    if "on" not in doc and True not in doc:
        problems.append("no `on:` trigger, so this workflow can never run")

    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        problems.append("no jobs, so a run would complete with nothing executed")
        return problems

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            problems.append(f"job {job_name}: not a mapping")
            continue
        if "uses" in job:
            continue  # reusable workflow call; steps live elsewhere
        if "runs-on" not in job:
            problems.append(f"job {job_name}: no runs-on")
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"job {job_name}: no steps")
            continue
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                problems.append(f"job {job_name} step {i}: not a mapping")
                continue
            # Exactly one of uses/run. A step with neither is silently skipped;
            # a step with both is rejected at startup.
            has_uses, has_run = "uses" in step, "run" in step
            if has_uses and has_run:
                problems.append(
                    f"job {job_name} step {i} ({step.get('name', '?')}): has BOTH uses and run")
            elif not has_uses and not has_run:
                problems.append(
                    f"job {job_name} step {i} ({step.get('name', '?')}): has NEITHER uses nor run")
    return problems


def main() -> int:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        print(f"no workflow files under {WORKFLOWS}", file=sys.stderr)
        return 1

    failed = 0
    for f in files:
        problems = check(f)
        if problems:
            failed += 1
            print(f"FAIL {f.name}")
            for p in problems:
                print(f"       {p}")
        else:
            print(f"  ok {f.name}")

    print(f"\n{len(files)} workflow(s), {failed} with problems")
    if failed:
        print("These would start-fail on GitHub, which reports as NO CHECKS "
              "rather than a failing check -- the PR just sits there.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
