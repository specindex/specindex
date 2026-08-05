"""HTTP with a MANDATORY soft-404 baseline.

Government and .edu hosts routinely answer unknown paths with HTTP 200 and
their landing page. Believing status codes has produced, in this codebase
alone: 17 fabricated EDMS "discoveries", a fabricated WBDG index URL that
returned exactly 1,359 bytes (byte-identical to the baseline) beside a real
file path in the same answer, and a whole SPA site read as empty because its
catch-all shell matched every real page.

So `get()` cannot be called without the host having been baselined. That is
enforced, not documented -- a discipline that depends on remembering is a
discipline that lapses.
"""
from __future__ import annotations

import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_baselines: dict[str, tuple[bool, int]] = {}


def _host(url: str) -> str:
    p = urllib.parse.urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def raw(url: str, timeout: float = 30.0) -> tuple[int | None, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except Exception as e:  # noqa: BLE001 -- any failure means "do not trust this url"
        return getattr(e, "code", None), b"", f"error:{type(e).__name__}"


def baseline(url: str) -> tuple[bool, int]:
    """(host_soft_404s, baseline_len). Cached per host."""
    h = _host(url)
    if h not in _baselines:
        st, body, _ = raw(f"{h}/zzzz-nonexistent-specindex-baseline/", timeout=20)
        _baselines[h] = (st == 200, len(body))
    return _baselines[h]


def get(url: str, timeout: float = 30.0, allow_soft404_host: bool = False):
    """Fetch, having baselined the host first.

    Returns (ok, status, body, ctype). `ok` is False when the response cannot
    be distinguished from the host's catch-all page -- a 200 that means
    nothing. On a soft-404 host, callers that legitimately cannot use length
    discrimination (SPA sites, where the shell and every real page are
    byte-identical) must opt in explicitly via allow_soft404_host, so the
    weaker guarantee is a visible decision rather than an accident.
    """
    soft, blen = baseline(url)
    st, body, ct = raw(url, timeout)
    if st != 200 or not body:
        return False, st, body, ct
    if soft and not allow_soft404_host and abs(len(body) - blen) < 512:
        return False, st, body, "soft-404"
    return True, st, body, ct


def is_document(ctype: str, body: bytes, min_bytes: int = 2048) -> bool:
    """Verify by CONTENT, never by status. A 200-with-HTML-error-page must
    never land in the bucket as a document."""
    ct = (ctype or "").lower()
    return (len(body) >= min_bytes
            and any(c in ct for c in ("application/pdf", "officedocument", "msword",
                                      "application/zip", "octet-stream")))
