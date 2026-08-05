"""Progress logging for long loops.

The O(k^2) dedupe ran for HOURS at 100% CPU printing nothing, because it only
printed at the end. With no rate and no ETA there is no way to tell a slow job
from a hung one, and the standing instruction became "kill it and reroute" --
which is right, but sometimes kills healthy work. A capture run was killed on
exactly that reasoning with a provably-good tenant next in the queue.

Rule: any loop that can exceed ~30 seconds emits rate and ETA.
"""
from __future__ import annotations

import sys
import time


class Progress:
    def __init__(self, total: int | None, label: str, every: int = 25,
                 stream=sys.stderr) -> None:
        self.total = total
        self.label = label
        self.every = max(1, every)
        self.n = 0
        self.t0 = time.time()
        self.stream = stream

    def tick(self, k: int = 1, note: str = "") -> None:
        self.n += k
        if self.n % self.every and (self.total is None or self.n != self.total):
            return
        el = max(1e-6, time.time() - self.t0)
        rate = self.n / el
        if self.total:
            eta = (self.total - self.n) / rate if rate > 0 else float("inf")
            pct = 100.0 * self.n / self.total
            msg = (f"[{self.label}] {self.n:,}/{self.total:,} ({pct:.1f}%) "
                   f"{rate:.1f}/s eta {eta/60:.1f}m")
        else:
            msg = f"[{self.label}] {self.n:,} {rate:.1f}/s {el/60:.1f}m elapsed"
        print(f"{msg} {note}".rstrip(), file=self.stream, flush=True)

    def done(self) -> None:
        el = time.time() - self.t0
        print(f"[{self.label}] DONE {self.n:,} in {el/60:.2f}m "
              f"({self.n/max(1e-6, el):.1f}/s)", file=self.stream, flush=True)
