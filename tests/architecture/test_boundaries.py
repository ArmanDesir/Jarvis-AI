import ast
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


def test_openai_sdk_is_isolated_to_provider_infrastructure() -> None:
    allowed = ROOT / "packages/core/src/rightjob/provider_adapters"
    offenders = []
    for path in ROOT.glob("packages/**/*.py"):
        if any(part in {".venv", ".tooling"} for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8")
        if ("import openai" in source or "from openai" in source) and not path.is_relative_to(
            allowed
        ):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_ai_runtime_composes_adapter_without_importing_openai_sdk() -> None:
    runtime = ROOT / "packages/core/src/rightjob/ai_runtime"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in runtime.glob("*.py"))
    assert "rightjob.provider_adapters" in sources
    assert "import openai" not in sources
    assert "from openai" not in sources


def test_executive_uses_only_its_module_and_published_contracts() -> None:
    executive = ROOT / "packages/core/src/rightjob/executive"
    offenders: list[tuple[str, str]] = []
    for path in executive.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            if (
                module
                and module.startswith("rightjob.")
                and not module.startswith(("rightjob.contracts", "rightjob.executive"))
            ):
                offenders.append((path.name, module))
    assert offenders == []


def test_validation_and_reviewer_have_no_authority_or_runtime_dependencies() -> None:
    forbidden = {
        "rightjob.orchestration",
        "rightjob.policy",
        "rightjob.provider_adapters",
        "rightjob.repositories",
        "rightjob.tool_interfaces",
        "sqlalchemy",
        "temporalio",
    }
    offenders: list[tuple[str, str]] = []
    for boundary in ("validation", "reviewer"):
        boundary_forbidden = forbidden | (
            {
                "rightjob.contracts.approval",
                "rightjob.contracts.authorization",
                "rightjob.contracts.policy",
            }
            if boundary == "reviewer"
            else set()
        )
        for path in (ROOT / f"packages/core/src/rightjob/{boundary}").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                if module and any(
                    module == item or module.startswith(f"{item}.") for item in boundary_forbidden
                ):
                    offenders.append((path.relative_to(ROOT).as_posix(), module))
    assert offenders == []


def test_ai_router_has_no_authority_adapter_or_runtime_dependencies() -> None:
    forbidden = {
        "rightjob.contracts.approval",
        "rightjob.contracts.authorization",
        "rightjob.contracts.policy",
        "rightjob.executive",
        "rightjob.orchestration",
        "rightjob.planner",
        "rightjob.policy",
        "rightjob.provider_adapters",
        "rightjob.registry",
        "rightjob.repositories",
        "rightjob.reviewer",
        "rightjob.tool_interfaces",
        "rightjob.validation",
        "rightjob_worker",
        "aiohttp",
        "anthropic",
        "builtins",
        "glob",
        "groq",
        "httpx",
        "importlib",
        "inspect",
        "openai",
        "os",
        "pathlib",
        "pkgutil",
        "requests",
        "shutil",
        "socket",
        "sys",
        "sqlalchemy",
        "tempfile",
        "temporalio",
        "urllib",
    }
    offenders: list[tuple[str, str]] = []
    for path in (ROOT / "packages/core/src/rightjob/ai_router").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = (
                [node.module]
                if isinstance(node, ast.ImportFrom) and node.module
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for module in modules:
                if any(module == item or module.startswith(f"{item}.") for item in forbidden):
                    offenders.append((path.relative_to(ROOT).as_posix(), module))
        forbidden_calls = {
            "__import__",
            "compile",
            "delattr",
            "eval",
            "exec",
            "getattr",
            "globals",
            "locals",
            "open",
            "setattr",
            "vars",
        }
        offenders.extend(
            (path.relative_to(ROOT).as_posix(), node.func.id)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
        )
    assert offenders == []


def test_result_presentation_contract_has_no_payload_or_authority_fields() -> None:
    from dataclasses import fields

    from rightjob.contracts.review import ExecutiveResultPresentation, ReviewAssessment

    forbidden = {
        "payload",
        "payload_json",
        "approval",
        "authorization",
        "workflow_state",
        "repository",
        "credential",
        "provider_response",
    }
    assert not ({field.name for field in fields(ExecutiveResultPresentation)} & forbidden)
    assert not ({field.name for field in fields(ReviewAssessment)} & forbidden)


def test_quality_gate_decisions_have_no_provider_authority_or_runtime_dependencies() -> None:
    path = ROOT / "packages/core/src/rightjob/orchestration/application/quality_gate.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "rightjob.ai_router",
        "rightjob.contracts.approval",
        "rightjob.contracts.authorization",
        "rightjob.contracts.policy",
        "rightjob.policy",
        "rightjob.provider_adapters",
        "rightjob.repositories",
        "rightjob.tool_interfaces",
        "rightjob_worker",
        "aiohttp",
        "anthropic",
        "httpx",
        "openai",
        "requests",
        "sqlalchemy",
        "temporalio",
    }
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    assert not {
        imported
        for imported in imports
        if any(imported == item or imported.startswith(f"{item}.") for item in forbidden)
    }


def test_reviewer_and_executive_do_not_mutate_quality_gate_state() -> None:
    for boundary in ("reviewer", "executive"):
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / f"packages/core/src/rightjob/{boundary}").glob("*.py")
        )
        assert "QualityGateDecisionService" not in sources
        assert "rightjob.orchestration.application.quality_gate" not in sources
