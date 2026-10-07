# -*- coding: utf-8 -*-
"""
NFR-01/NFR-02 performance benchmark.

I (Claude) can't run this myself - my sandbox has no GCP credentials or
GPU, so it can't call real Vision API/Qwen2-VL. Run this yourself against
your live server with real documents to get real numbers.

Usage:
    1. Start your server: python3 -m uvicorn main:app --port 8000
       (make sure OCR_ENGINE=vision or qwen2vl in .env - NOT mock,
       since mock is near-instant and won't tell you anything real)
    2. python3 scripts/benchmark_performance.py path/to/real_document.pdf

What it measures:
    NFR-01: single-request timing (target: <=15s for <=5 pages)
    NFR-02: 20 concurrent requests, checking degradation vs. baseline
            (target: <30% slower than a single request's baseline time)
"""
import sys
import time
import statistics
import concurrent.futures

import requests

API_URL = "http://localhost:8000/analyze"
CONCURRENT_REQUESTS = 20  # NFR-02's exact target


def single_request(file_path: str) -> dict:
    """Sends one request, returns timing info from both the client side
    (wall clock, includes network) and the server side (from the response
    body, excludes network - useful to separate "slow network" from
    "slow processing")."""
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    client_start = time.monotonic()
    response = requests.post(API_URL, files={"file": (file_path, file_bytes)})
    client_elapsed = time.monotonic() - client_start

    if response.status_code != 200:
        return {"success": False, "status": response.status_code, "detail": response.text, "client_time": client_elapsed}

    data = response.json()
    return {
        "success": True,
        "client_time": client_elapsed,
        "server_time": data["processing_time_seconds"],
        "ocr_time": data["ocr_time_seconds"],
        "risk_time": data["risk_detection_time_seconds"],
        "clause_count": data["clause_count"],
    }


def run_nfr01(file_path: str):
    print("=" * 60)
    print("NFR-01: single-request timing (target: <=15s for <=5 pages)")
    print("=" * 60)
    result = single_request(file_path)
    if not result["success"]:
        print(f"FAILED - status {result['status']}: {result['detail']}")
        return None

    print(f"Client-observed time (includes network): {result['client_time']:.2f}s")
    print(f"Server-reported total time:               {result['server_time']:.2f}s")
    print(f"  - OCR stage:                             {result['ocr_time']:.2f}s")
    print(f"  - Risk detection stage:                  {result['risk_time']:.2f}s")
    print(f"Clauses analyzed: {result['clause_count']}")
    verdict = "PASS" if result["server_time"] <= 15 else "FAIL"
    print(f"\nNFR-01 verdict: {verdict} (target: <=15s)")
    return result["client_time"]


def run_nfr02(file_path: str, baseline_time: float):
    print()
    print("=" * 60)
    print(f"NFR-02: {CONCURRENT_REQUESTS} concurrent requests (target: <30% degradation)")
    print("=" * 60)
    print(f"Baseline (single request): {baseline_time:.2f}s")
    print(f"Firing {CONCURRENT_REQUESTS} requests simultaneously...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = [executor.submit(single_request, file_path) for _ in range(CONCURRENT_REQUESTS)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    print(f"\nSucceeded: {len(successes)}/{CONCURRENT_REQUESTS}")
    if failures:
        print(f"FAILED: {len(failures)} requests errored out:")
        for f in failures[:5]:
            print(f"  - status {f.get('status')}: {f.get('detail', '')[:100]}")

    if not successes:
        print("\nNFR-02 verdict: FAIL (no requests succeeded)")
        return

    times = [r["client_time"] for r in successes]
    avg_time = statistics.mean(times)
    max_time = max(times)
    degradation_pct = ((avg_time - baseline_time) / baseline_time) * 100

    print(f"\nAverage concurrent response time: {avg_time:.2f}s")
    print(f"Max concurrent response time:     {max_time:.2f}s")
    print(f"Degradation vs baseline:          {degradation_pct:+.1f}%")

    verdict = "PASS" if degradation_pct <= 30 and len(successes) == CONCURRENT_REQUESTS else "FAIL"
    print(f"\nNFR-02 verdict: {verdict} (target: <30% degradation, all {CONCURRENT_REQUESTS} requests succeeding)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/benchmark_performance.py path/to/real_document.pdf")
        sys.exit(1)

    file_path = sys.argv[1]
    baseline = run_nfr01(file_path)
    if baseline is not None:
        run_nfr02(file_path, baseline)