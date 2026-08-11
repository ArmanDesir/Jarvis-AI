import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dependency_boundaries() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_architecture.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_phase1_scope() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_phase1_scope.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_temporal_sdk_is_isolated_to_worker_infrastructure() -> None:
    allowed = ROOT / "services/worker/src/rightjob_worker"
    offenders = []
    source_paths = [
        *ROOT.glob("packages/**/*.py"),
        *ROOT.glob("apps/**/*.py"),
        *ROOT.glob("services/**/*.py"),
    ]
    for path in source_paths:
        if any(part in {".venv", ".tooling"} for part in path.parts):
            continue
        if "temporalio" in path.read_text(encoding="utf-8") and not path.is_relative_to(allowed):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []
