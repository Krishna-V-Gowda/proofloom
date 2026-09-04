#!/usr/bin/env python3
"""Fail-closed public-tree scanner for obvious secrets and generated residue."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
excluded = {
    ".git", ".venv", "venv", "node_modules", ".next", "build", "dist",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
forbidden_files = {".env", "id_rsa", "id_ed25519"}
patterns = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Razorpay live key", re.compile(r"rzp_live_[A-Za-z0-9]+")),
]
failures: list[str] = []
scanned = 0
for path in sorted(root.rglob("*")):
    if any(part in excluded for part in path.parts):
        continue
    if path.is_symlink():
        failures.append(f"symlink: {path.relative_to(root)}")
        continue
    if not path.is_file():
        continue
    rel = path.relative_to(root)
    if path.resolve() == Path(__file__).resolve():
        continue
    if path.name in forbidden_files or (path.name.startswith(".env.") and path.name != ".env.example"):
        failures.append(f"forbidden file: {rel}")
        continue
    if path.stat().st_size > 5_000_000:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    scanned += 1
    for label, pattern in patterns:
        if pattern.search(text):
            failures.append(f"{label}: {rel}")
    if "/Users/" in text or "/mnt/data/" in text:
        failures.append(f"local absolute path: {rel}")
if failures:
    print(json.dumps({"status": "fail", "failures": failures}, indent=2))
    raise SystemExit(1)
print(json.dumps({"status": "pass", "scanned_text_files": scanned}, indent=2))
