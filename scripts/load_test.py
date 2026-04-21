"""Simple load-test — hit common public endpoints in parallel, measure p95.

Use before launch to confirm the static+API stack holds under Reddit-scale traffic.

Usage:
    python scripts/load_test.py
    python scripts/load_test.py --url http://127.0.0.1:8005 --users 50 --duration 30

Not a replacement for k6/wrk — designed to need zero install and run from
the same Python already on the box.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import random
import sys
import time
from dataclasses import dataclass, field
from statistics import mean, median
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_PATHS = [
    "/app/",
    "/app/browse/",
    "/app/collections/",
    "/app/graph/",
    "/app/timeline/",
    "/app/map/",
    "/app/about/",
    "/app/about/methodology/",
    "/app/api-docs/",
    "/app/changelog/",
    "/entities/?per_page=25",
    "/stats/",
    "/integrity/stats",
    "/collections/",
    "/search/?q=orisha",
    "/graph/?max_nodes=100",
]


@dataclass
class Result:
    path: str
    status: int
    duration_ms: float


@dataclass
class Summary:
    total: int = 0
    errors: int = 0
    durations: list[float] = field(default_factory=list)

    def record(self, r: Result) -> None:
        self.total += 1
        if r.status >= 400:
            self.errors += 1
        self.durations.append(r.duration_ms)


def _fetch(base: str, path: str, timeout: float) -> Result:
    url = base.rstrip("/") + path
    req = Request(url, headers={"User-Agent": "realms-loadtest/1"})
    start = time.perf_counter()
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read(1024)
            status = resp.status
    except HTTPError as e:
        status = e.code
    except (URLError, TimeoutError) as e:
        status = 599
    except Exception:  # noqa: BLE001
        status = 599
    dur = (time.perf_counter() - start) * 1000
    return Result(path=path, status=status, duration_ms=dur)


def _p(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = int(len(s) * q)
    return s[min(k, len(s) - 1)]


def run(base: str, users: int, duration: float, paths: list[str]) -> dict:
    per_path: dict[str, Summary] = {p: Summary() for p in paths}
    end = time.time() + duration

    def worker():
        while time.time() < end:
            path = random.choice(paths)
            r = _fetch(base, path, timeout=10.0)
            per_path[path].record(r)

    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
        futs = [pool.submit(worker) for _ in range(users)]
        concurrent.futures.wait(futs)

    overall: Summary = Summary()
    for s in per_path.values():
        overall.total += s.total
        overall.errors += s.errors
        overall.durations.extend(s.durations)

    lines = [
        f"base: {base}",
        f"concurrent users: {users}",
        f"duration: {duration}s",
        f"total requests: {overall.total}",
        f"errors: {overall.errors} ({overall.errors / max(1, overall.total) * 100:.1f}%)",
        f"throughput: {overall.total / duration:.1f} req/s",
        "",
        f"latency median: {median(overall.durations) if overall.durations else 0:.0f} ms",
        f"latency mean:   {mean(overall.durations) if overall.durations else 0:.0f} ms",
        f"latency p95:    {_p(overall.durations, 0.95):.0f} ms",
        f"latency p99:    {_p(overall.durations, 0.99):.0f} ms",
        "",
        "per-path p95 (ms) / errors / total:",
    ]
    for p, s in per_path.items():
        p95 = _p(s.durations, 0.95)
        lines.append(f"  {p95:6.0f}  {s.errors:4d}  {s.total:5d}  {p}")
    return {"text": "\n".join(lines), "overall": overall, "per_path": per_path}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8005")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--paths", nargs="*", default=DEFAULT_PATHS)
    args = ap.parse_args()

    summary = run(args.url, args.users, args.duration, args.paths)
    print(summary["text"])

    # Exit non-zero if error rate > 1% or p95 > 2000ms.
    ov: Summary = summary["overall"]
    err_rate = ov.errors / max(1, ov.total)
    p95 = _p(ov.durations, 0.95)
    if err_rate > 0.01:
        print(f"\nFAIL: error rate {err_rate * 100:.1f}% exceeds 1%")
        return 1
    if p95 > 2000:
        print(f"\nFAIL: p95 {p95:.0f}ms exceeds 2s budget")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
