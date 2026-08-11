"""Reject committed environment files and obvious credential assignments."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".tooling", ".venv", "node_modules", ".next", "dist", "build"}
ASSIGNMENT = re.compile(
    r"""(?i)(api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['"]?[^\s'"]{12,}"""
)


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            failures.append(f"{path}: environment files must not be committed")
            continue
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".yaml", ".yml"}:
            continue
        if ASSIGNMENT.search(path.read_text(encoding="utf-8", errors="ignore")):
            failures.append(f"{path}: possible embedded secret")
    if failures:
        print("\n".join(failures))
        return 1
    print("Secret hygiene: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
