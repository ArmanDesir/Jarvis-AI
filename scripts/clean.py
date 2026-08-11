"""Remove only known generated artifacts inside this repository."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", "dist", "build"}
SUFFIXES = {".egg-info"}

for path in sorted(ROOT.rglob("*"), reverse=True):
    if path.is_dir() and (path.name in NAMES or any(path.name.endswith(s) for s in SUFFIXES)):
        shutil.rmtree(path)
