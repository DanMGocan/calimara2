#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse


DEFAULT_ENDPOINTS = [
    "/",
    "/api/statistici/platforma",
    "/api/prima-pagina?category=toate",
    "/robots.txt",
    "/sitemap.xml",
]


def percentile(values: list[float], rank: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((rank / 100) * (len(ordered) - 1)))))
    return ordered[index]


def request_once(parsed_base, path: str, timeout: float) -> tuple[int | None, float, int]:
    started = time.perf_counter()
    connection_class = http.client.HTTPSConnection if parsed_base.scheme == "https" else http.client.HTTPConnection
    port = parsed_base.port
    host = parsed_base.hostname or "127.0.0.1"
    connection = connection_class(host, port=port, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Host": parsed_base.netloc, "User-Agent": "calimara-capacity-benchmark/1.0"})
        response = connection.getresponse()
        body = response.read()
        elapsed = (time.perf_counter() - started) * 1000
        return response.status, elapsed, len(body)
    finally:
        connection.close()


def run_once(base_url: str, endpoints: list[str], concurrency: int, duration: int, timeout: float) -> dict:
    parsed_base = urlparse(base_url)
    deadline = time.perf_counter() + duration
    lock = threading.Lock()
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    bytes_read = 0
    errors = 0

    def worker(worker_id: int) -> None:
        nonlocal bytes_read, errors
        index = worker_id
        while time.perf_counter() < deadline:
            path = endpoints[index % len(endpoints)]
            index += concurrency
            try:
                status, latency, size = request_once(parsed_base, path, timeout)
                status_key = str(status)
                with lock:
                    latencies.append(latency)
                    statuses[status_key] = statuses.get(status_key, 0) + 1
                    bytes_read += size
            except Exception as exc:
                with lock:
                    errors += 1
                    statuses[exc.__class__.__name__] = statuses.get(exc.__class__.__name__, 0) + 1

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        for worker_id in range(concurrency):
            executor.submit(worker, worker_id)
    elapsed = max(time.perf_counter() - started, 0.001)
    ok = sum(count for status, count in statuses.items() if status.isdigit() and 200 <= int(status) < 400)
    total = len(latencies) + errors
    return {
        "concurrency": concurrency,
        "duration_seconds": round(elapsed, 2),
        "requests": total,
        "ok": ok,
        "errors": errors,
        "rps": round(total / elapsed, 2),
        "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
        "p50_ms": round(percentile(latencies, 50), 2),
        "p95_ms": round(percentile(latencies, 95), 2),
        "p99_ms": round(percentile(latencies, 99), 2),
        "mb_read": round(bytes_read / 1024 / 1024, 2),
        "statuses": ";".join(f"{key}:{value}" for key, value in sorted(statuses.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a simple read-only capacity benchmark against Calimara.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL to test.")
    parser.add_argument("--duration", type=int, default=30, help="Seconds per concurrency level.")
    parser.add_argument("--concurrency", default="10,25,50,100,200", help="Comma-separated concurrency levels.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds.")
    parser.add_argument("--endpoint", action="append", dest="endpoints", help="Endpoint path to include. Can be repeated.")
    args = parser.parse_args()

    endpoints = args.endpoints or DEFAULT_ENDPOINTS
    concurrencies = [int(item.strip()) for item in args.concurrency.split(",") if item.strip()]
    fields = ["concurrency", "duration_seconds", "requests", "ok", "errors", "rps", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "mb_read", "statuses"]
    print(",".join(fields))
    for concurrency in concurrencies:
        result = run_once(args.base_url, endpoints, concurrency, args.duration, args.timeout)
        print(",".join(str(result[field]) for field in fields))


if __name__ == "__main__":
    main()
