"""Prevent Phase 1 from acquiring business routes or proof-gate dependencies."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api/src/rightjob_api"
ALLOWED_ROUTES = {
    "/health",
    "/ready",
    "/version",
    "/identity/context",
    "/api/v1/me",
    "/api/v1/workspace",
    "/api/v1/membership",
}
PROOF_DEPENDENCIES = {"clerk", "pgvector", "redis", "openai", "anthropic"}


def main() -> int:
    failures: list[str] = []
    routes: set[str] = set()
    for path in API.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        prefix_match = re.search(r'APIRouter\(prefix="([^"]+)"', source)
        prefix = prefix_match.group(1) if prefix_match else ""
        routes.update(
            prefix + route
            for route in re.findall(
                r'@(?:app|router)\.(?:get|post|put|patch|delete)\(\s*"([^"]+)"', source
            )
        )
    if routes != ALLOWED_ROUTES:
        failures.append(
            f"Phase 1 API routes must be exactly {sorted(ALLOWED_ROUTES)}; got {routes}"
        )

    manifests = [
        ROOT / "pyproject.toml",
        *(path for path in ROOT.glob("**/pyproject.toml") if ".tooling" not in path.parts),
    ]
    dependency_text = "\n".join(path.read_text(encoding="utf-8").lower() for path in manifests)
    for dependency in PROOF_DEPENDENCIES:
        if re.search(rf'["\']{dependency}(?:\[|[<>=~"\'])', dependency_text):
            failures.append(
                f"Proof-gate/external dependency is prohibited in Phase 1: {dependency}"
            )

    temporal_manifests = [
        path.relative_to(ROOT).as_posix()
        for path in manifests
        if re.search(r'["\']temporalio(?:\[|[<>=~"\'])', path.read_text(encoding="utf-8").lower())
    ]
    if temporal_manifests != ["services/worker/pyproject.toml"]:
        failures.append(
            f"Temporal SDK must remain isolated to services/worker; found {temporal_manifests}"
        )

    if failures:
        print("\n".join(failures))
        return 1
    print("Phase 1 scope: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
