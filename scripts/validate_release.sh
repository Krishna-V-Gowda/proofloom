#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/proofloom-verify.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src"

printf '%s\n' '[1/9] required public artifacts'
for path in README.md pyproject.toml requirements-lock.txt src/proofloom/engine.py src/proofloom/api.py tests/test_engine.py evaluation/results.json docs/ARCHITECTURE.md SECURITY.md; do
  test -f "$path"
done

printf '%s\n' '[2/9] source compilation without bytecode'
python3 - <<'PY'
from pathlib import Path
paths = sorted(Path('src').rglob('*.py')) + sorted(Path('tests').rglob('*.py')) + sorted(Path('scripts').rglob('*.py'))
for path in paths:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
print(f'compiled {len(paths)} Python files')
PY

printf '%s\n' '[3/9] behavior, API, audit, adapter and evaluation tests'
python3 -m pytest -q -p no:cacheprovider

printf '%s\n' '[4/9] deterministic 185-record seed'
python3 -m proofloom.cli export-data --output "$TMP/data" >/dev/null
python3 - "$TMP/data/manifest.json" <<'PY'
import json, sys
value=json.load(open(sys.argv[1]))
assert value['records']==185
print('seed inventory verified')
PY

printf '%s\n' '[5/9] held-out evaluation reproduction'
python3 -m proofloom.cli evaluate --output "$TMP/evaluation" --bootstrap-resamples 500 >/dev/null
python3 - "$TMP/evaluation/results.json" evaluation/results.json <<'PY'
import json, math, sys

fresh=json.load(open(sys.argv[1]))
retained=json.load(open(sys.argv[2]))

def equivalent(a, b, *, path='root'):
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)

    if type(a) is not type(b):
        return False

    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(equivalent(a[key], b[key], path=f'{path}.{key}') for key in a)

    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(
            equivalent(x, y, path=f'{path}[{i}]')
            for i, (x, y) in enumerate(zip(a, b))
        )

    return a == b

for key in (
    'dataset',
    'model',
    'pair_classifier_held_out',
    'policy_comparison',
    'merchant_bootstrap',
    'stress_test',
    'economics',
    'limitations',
):
    assert equivalent(fresh[key], retained[key], path=key), f'mismatch in {key}'

print('retained evaluation reproduced semantically')

PY

printf '%s\n' '[6/9] bounded benchmark smoke'
python3 -m proofloom.cli benchmark --output "$TMP/benchmarks" >/dev/null
test -s "$TMP/benchmarks/results.json"

printf '%s\n' '[7/9] public-source security scan'
python3 scripts/verify_public_tree.py .

printf '%s\n' '[8/9] documentation and asset links'
python3 - <<'PY'
from pathlib import Path
import re
root=Path('.')
for md in root.rglob('*.md'):
    if any(part in {'.git','.venv','node_modules'} for part in md.parts): continue
    text=md.read_text(encoding='utf-8')
    for target in re.findall(r'\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)', text):
        clean=target.split('#',1)[0]
        if clean and not (md.parent/clean).resolve().exists():
            raise SystemExit(f'broken relative link in {md}: {target}')
print('relative Markdown links verified')
PY

printf '%s\n' '[9/9] generated-residue guard'
if find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .venv -o -name node_modules -o -name .next -o -name build -o -name dist \) -print -quit | grep -q .; then
  echo 'generated residue detected' >&2
  find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .venv -o -name node_modules -o -name .next -o -name build -o -name dist \) -print >&2
  exit 1
fi
printf '%s\n' 'Proofloom release verification passed.'
