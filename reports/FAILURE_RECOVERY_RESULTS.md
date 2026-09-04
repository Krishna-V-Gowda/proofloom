# Failure-recovery results

The retained failure outputs are generated from the same fixed 185-record hero fixture used by the operator UI.

| Scenario | Detection | Safe behavior | Evidence |
|---|---|---|---|
| Duplicate webhook | repeated event ID observed | one replayed delivery suppressed; no duplicate decision | `demo/failure_results.json` |
| Model outage | ambiguity model made unavailable | exact and split paths continue; damaged-reference item stays open | `tests/test_engine.py`, `demo/failure_results.json` |
| Unsafe adjustment | reviewer requests amount different from immutable settlement fact | operation rejected and audit entry emitted | `tests/test_service.py`, `demo/failure_results.json` |
| Audit tamper | copied historical payload changed | first invalid sequence detected; live chain remains valid | `tests/test_audit.py`, `demo/failure_results.json` |
| 137-paise tie-out | source composition differs from reported settlement | close blocked before candidate ownership is evaluated | `tests/test_engine.py`, `demo/hero_result.json` |

The failure laboratory is not chaos testing or production resilience evidence. It proves the documented prototype behavior for these controlled cases.
