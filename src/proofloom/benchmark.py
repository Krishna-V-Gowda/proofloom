"""Local benchmark harness with explicit scope and raw repetitions."""
from __future__ import annotations

import json
from pathlib import Path
import platform
import statistics
import time
from typing import Any, Callable

from fastapi.testclient import TestClient

from .api import create_app
from .data import generate_evaluation_dataset, generate_hero_dataset
from .engine import CloseEngine
from .intelligence import AmbiguityModel


def measure(work: Callable[[], Any], *, repetitions: int, warmups: int = 5) -> dict[str, Any]:
    for _ in range(warmups):
        work()
    raw = []
    for _ in range(repetitions):
        start = time.perf_counter()
        work()
        raw.append(time.perf_counter() - start)
    ordered = sorted(raw)
    p95_index = min(len(ordered) - 1, max(0, int(round(0.95 * len(ordered) + 0.5)) - 1))
    return {
        "repetitions": repetitions,
        "warmups": warmups,
        "seconds": raw,
        "median_seconds": statistics.median(raw),
        "p95_seconds": ordered[p95_index],
    }


def run_benchmarks(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    evaluation = generate_evaluation_dataset()
    model = AmbiguityModel.train(evaluation)
    test_groups = set(evaluation.merchant_groups[20:24])
    pairs = [pair for pair in evaluation.pairs if pair.merchant_id in test_groups]
    dataset = generate_hero_dataset()

    score_result = measure(lambda: model.score_evaluation_pairs(pairs), repetitions=20)
    score_result["records_per_repetition"] = len(pairs)
    score_result["throughput_per_second"] = len(pairs) / score_result["median_seconds"]

    close_result = measure(lambda: CloseEngine(model=model).run(dataset), repetitions=20)
    close_result["source_records_per_repetition"] = dataset.source_record_count

    app = create_app()
    client = TestClient(app)
    client.post("/api/run-close")
    api_result = measure(lambda: client.get("/api/overview").raise_for_status(), repetitions=30)

    result = {
        "generated_at": "2026-09-04",
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "scope": "local process measurements; excludes production networking, persistence, multi-tenancy and browser rendering",
        "workloads": {
            "candidate_pair_scoring": score_result,
            "hero_close_core": close_result,
            "in_process_overview_api": api_result,
        },
    }
    (output / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = f"""# Proofloom benchmark results

## Environment

- Platform: `{result['environment']['platform']}`
- Python: `{result['environment']['python']}`
- Scope: {result['scope']}.

## Results

| Workload | Repetitions | Median | p95 | Interpretation |
|---|---:|---:|---:|---|
| Score {len(pairs):,} held-out candidate pairs | {score_result['repetitions']} | {score_result['median_seconds']*1000:.3f} ms | {score_result['p95_seconds']*1000:.3f} ms | {score_result['throughput_per_second']:,.0f} pairs/s in this process |
| Close 4 settlements / {dataset.source_record_count} source records | {close_result['repetitions']} | {close_result['median_seconds']*1000:.3f} ms | {close_result['p95_seconds']*1000:.3f} ms | includes candidate scoring; in-memory only |
| In-process overview API | {api_result['repetitions']} | {api_result['median_seconds']*1000:.3f} ms | {api_result['p95_seconds']*1000:.3f} ms | excludes network and browser rendering |

Five warm-ups preceded every workload. Raw repetitions are retained in `results.json`. These numbers are reproducible local observations—not a production capacity claim, service-level objective, or comparison with Razorpay infrastructure.
"""
    (output / "results.md").write_text(text, encoding="utf-8")
    return result
