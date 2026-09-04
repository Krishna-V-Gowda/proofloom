# Proofloom benchmark results

## Environment

- Platform: `Linux-6.18.35-x86_64-with-glibc2.41`
- Python: `3.13.5`
- Scope: local process measurements; excludes production networking, persistence, multi-tenancy and browser rendering.

## Results

| Workload | Repetitions | Median | p95 | Interpretation |
|---|---:|---:|---:|---|
| Score 1,008 held-out candidate pairs | 20 | 66.668 ms | 72.263 ms | 15,120 pairs/s in this process |
| Close 4 settlements / 185 source records | 20 | 1.638 ms | 2.190 ms | includes candidate scoring; in-memory only |
| In-process overview API | 30 | 1.468 ms | 5.156 ms | excludes network and browser rendering |

Five warm-ups preceded every workload. Raw repetitions are retained in `results.json`. These numbers are reproducible local observations—not a production capacity claim, service-level objective, or comparison with Razorpay infrastructure.
