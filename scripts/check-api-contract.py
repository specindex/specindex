#!/usr/bin/env python3
"""Assert every API path the FRONTEND calls actually exists in the API.

WHY THIS EXISTS. On 2026-08-05 the signup modal shipped to the live site while
`POST /v1/signup` did not exist in the deployed API. Every visitor who tried to
create an account got "Couldn't create your account -- try again in a moment."
It was not a moment: the endpoint was absent, so no retry could ever succeed,
and the copy told people the opposite. It stayed broken for a full day.

Three separate safeguards all failed to catch it, and each failed for its own
reason:

  * The frontend deploys on EVERY merge to main; the API deploys only when
    api/** changes. The two are independent by design, so a PR carrying a form
    and its endpoint ships the form first. That is not a bug -- but it means
    the frontend is routinely live against an older API, which is exactly the
    condition this check has to police.
  * The API deploy had been failing for three consecutive runs on IAM errors.
    Nothing announced that; the only record was a step summary nobody reads.
  * The deploy smoke test asserts /v1/projects returns ROWS -- a good check
    that is blind to this. A missing /v1/signup is not an empty result set on
    a route it tests; it is a route it never mentions.

So the gap is structural: nothing compared what the frontend CALLS against what
the API SERVES. This does exactly that, statically, at PR time -- before either
half deploys.

STATIC ON PURPOSE. It reads both sides from source, so it needs no credentials,
no running service, and no network, and it can therefore run on every PR
including from forks. --live additionally probes a deployed URL, which is what
the post-deploy step uses to prove the revision actually serves the routes.

A 404 is the failure. A 401/403/422 is a PASS -- it proves the route exists and
is merely refusing this particular unauthenticated or unshaped request, which
is the correct behaviour for most of these endpoints.

Usage:
  python3 scripts/check-api-contract.py
  python3 scripts/check-api-contract.py --live https://specindex-api-xxxx.a.run.app
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Where the frontend calls the API from. Template literals like
# `${API_BASE}/v1/projects?limit=1` and plain "/v1/signup" both appear.
FRONTEND_DIRS = ["app", "components", "lib"]
FRONTEND_CALL_RE = re.compile(r"""\$\{API_BASE\}(/v1/[^`"']*)""")

# FastAPI decorators in api/main.py.
ROUTE_RE = re.compile(
    r"""@app\.(get|post|put|patch|delete)\(\s*["']([^"']+)["']""", re.I)


def normalise(path: str) -> str:
    """Reduce a called path to something comparable with a declared route.

    Drops the query string, and collapses interpolated segments -- a call to
    `${API_BASE}/v1/projects/${id}` must match a declared `/v1/projects/{sk}`.
    Comparing raw strings would report every parameterised route as missing and
    the check would be ignored within a week.
    """
    # Strip ${...} with BALANCED braces. A naive [^}]* stops at the first
    # closing brace, so `${encodeURIComponent(sk)}` truncated to
    # `/v1/projects/${encodeURIComponent` and was reported as a missing route.
    # Three of the eighteen paths were false positives on the first run, which
    # is how a check like this gets ignored.
    out, i = [], 0
    while i < len(path):
        if path.startswith("${", i):
            depth, j = 1, i + 2
            while j < len(path) and depth:
                if path[j] == "{":
                    depth += 1
                elif path[j] == "}":
                    depth -= 1
                j += 1
            # A whole segment (preceded by "/") is a path PARAMETER. Anything
            # else is an interpolated suffix -- a query string built elsewhere,
            # like `/v1/projects/facets${qs}` -- and is not part of the route.
            if out and out[-1] == "/":
                out.append("{}")
            i = j
            continue
        out.append(path[i])
        i += 1
    path = "".join(out).split("?")[0].split("#")[0]
    path = re.sub(r"\{[^}]*\}", "{}", path)
    return path.rstrip("/") or "/"


def matches_any(called: str, routes: set[str]) -> bool:
    """Does a called path correspond to at least one declared route?

    A "{}" on the CALLED side is a value the frontend computes at runtime, so
    it matches any single segment. lib/crm.ts builds
    `/v1/ops/customer/${uid}/${action}` where action is "deactivate" or
    "reactivate" -- both routes exist, but a plain string comparison reports the
    path as missing because no literal route is spelled `/{}/{}`.

    Literal segments still have to match exactly, so a genuine typo or a
    genuinely absent endpoint is still caught. Only the parts this script
    cannot know are treated as wildcards -- and treating them as anything else
    means reporting healthy code as broken.
    """
    if called in routes:
        return True
    cs = called.split("/")
    for r in routes:
        rs = r.split("/")
        if len(rs) != len(cs):
            continue
        if all(c == "{}" or r_ == "{}" or c == r_ for c, r_ in zip(cs, rs)):
            return True
    return False


def frontend_paths() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for d in FRONTEND_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for f in list(base.rglob("*.ts")) + list(base.rglob("*.tsx")):
            try:
                text = f.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            for m in FRONTEND_CALL_RE.finditer(text):
                p = normalise(m.group(1))
                if p and p != "/":
                    found.setdefault(p, []).append(
                        str(f.relative_to(ROOT)))
    return found


def api_routes() -> set[str]:
    main = ROOT / "api" / "main.py"
    if not main.is_file():
        print("FAIL: api/main.py not found", file=sys.stderr)
        raise SystemExit(2)
    return {normalise(m.group(2)) for m in ROUTE_RE.finditer(main.read_text())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", help="also probe this deployed base URL for 404s")
    args = ap.parse_args()

    calls = frontend_paths()
    routes = api_routes()
    print(f"frontend calls {len(calls)} distinct path(s); "
          f"api/main.py declares {len(routes)} route(s)\n")

    missing = {p: f for p, f in calls.items() if not matches_any(p, routes)}
    for p in sorted(calls):
        mark = "MISSING" if p in missing else "ok"
        print(f"  {mark:>8}  {p}")
        if p in missing:
            for f in sorted(set(missing[p])):
                print(f"            called from {f}")

    if missing:
        print(f"\nFAIL: {len(missing)} path(s) called by the frontend do not "
              f"exist in api/main.py.")
        print("The UI would show a generic error that no retry can fix.")
        return 1
    print("\nPASS: every frontend API path exists in api/main.py")

    if args.live:
        import urllib.error  # noqa: PLC0415
        import urllib.request  # noqa: PLC0415

        print(f"\nprobing {args.live}")
        live_fail = 0
        for p in sorted(calls):
            if "{}" in p:
                continue  # needs a real id; the static check already covered it
            url = args.live.rstrip("/") + p
            try:
                req = urllib.request.Request(
                    url, data=b"{}", method="POST",
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    code = r.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception as e:  # noqa: BLE001
                print(f"  SKIP  {p} ({type(e).__name__})")
                continue
            # 404 means the route is absent. 401/403/422/405 all prove it is
            # THERE and merely refusing this unauthenticated, unshaped probe.
            if code == 404:
                print(f"  MISSING  {p} -> 404 on the deployed revision")
                live_fail += 1
            else:
                print(f"       ok  {p} -> {code}")
        if live_fail:
            print(f"\nFAIL: {live_fail} route(s) return 404 on the deployed API.")
            return 1
        print("\nPASS: no frontend route 404s on the deployed API")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
