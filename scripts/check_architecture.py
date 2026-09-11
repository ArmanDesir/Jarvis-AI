"""Dependency-free enforcement of constitutional Python import boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "packages/core/src/rightjob"
DEPARTMENTS = ROOT / "departments"
CORE_MODULES = {
    "ai_runtime",
    "executive",
    "context",
    "planner",
    "orchestration",
    "policy",
    "work",
    "identity",
    "memory",
    "ai_router",
    "validation",
    "reviewer",
    "tool_interfaces",
    "provider_adapters",
    "repositories",
    "registry",
    "audit",
    "content",
    "usage",
}
ALLOWED_CORE_IMPORTS = {
    "shared",
    "contracts",
}
EXCEPTIONS = {
    "ai_runtime": {"executive", "planner", "provider_adapters"},
    "provider_adapters": {"tool_interfaces"},
}
STRICTLY_FORBIDDEN = {
    "ai_router": {
        "executive",
        "orchestration",
        "planner",
        "policy",
        "provider_adapters",
        "registry",
        "repositories",
        "reviewer",
        "tool_interfaces",
        "validation",
    },
    "ai_runtime": {
        "audit",
        "identity",
        "orchestration",
        "policy",
        "repositories",
        "tool_interfaces",
    },
    "executive": {"planner", "orchestration", "provider_adapters", "tool_interfaces"},
    "planner": {"orchestration", "provider_adapters", "tool_interfaces", "repositories"},
    "reviewer": {"orchestration", "policy", "provider_adapters", "tool_interfaces", "repositories"},
    "validation": {
        "orchestration",
        "policy",
        "provider_adapters",
        "tool_interfaces",
        "repositories",
    },
    "memory": {"work", "identity"},
    "tool_interfaces": {"provider_adapters"},
}
VENDOR_SDK_OWNERS = {"openai": "provider_adapters"}
FORBIDDEN_EXTERNAL_IMPORTS = {
    owner: {"importlib", "sqlalchemy", "subprocess", "temporalio"}
    for owner in {"ai_router", "executive", "reviewer", "validation"}
}
FORBIDDEN_EXTERNAL_IMPORTS["ai_router"].update(
    {
        "aiohttp",
        "anthropic",
        "builtins",
        "glob",
        "groq",
        "httpx",
        "inspect",
        "openai",
        "os",
        "pathlib",
        "pkgutil",
        "requests",
        "rightjob_worker",
        "shutil",
        "socket",
        "sys",
        "tempfile",
        "urllib",
    }
)
FORBIDDEN_CONTRACT_IMPORTS = {
    "ai_router": {
        "rightjob.contracts.approval",
        "rightjob.contracts.authorization",
        "rightjob.contracts.policy",
    },
    "reviewer": {
        "rightjob.contracts.approval",
        "rightjob.contracts.authorization",
        "rightjob.contracts.policy",
    },
}
FORBIDDEN_AI_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_ROUTER_CALLS = FORBIDDEN_AI_CALLS | {
    "delattr",
    "getattr",
    "globals",
    "locals",
    "open",
    "setattr",
    "vars",
}
QUALITY_GATE_FORBIDDEN_EXTERNAL_IMPORTS = {
    "aiohttp",
    "anthropic",
    "httpx",
    "importlib",
    "openai",
    "requests",
    "rightjob_worker",
    "socket",
    "subprocess",
    "temporalio",
    "urllib",
}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def core_module(path: Path) -> str | None:
    relative = path.relative_to(CORE)
    return relative.parts[0] if relative.parts and relative.parts[0] in CORE_MODULES else None


def check_core(path: Path) -> list[str]:
    source = core_module(path)
    if source is None:
        return []
    failures: list[str] = []
    quality_gate = source == "orchestration" and path.name in {
        "quality_gate.py",
        "revision_execution.py",
    }
    for imported in imports(path):
        if any(
            imported == forbidden or imported.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_CONTRACT_IMPORTS.get(source, set())
        ):
            failures.append(f"{path}: {source} must not import authority contract {imported}")
            continue
        external_root = imported.split(".", 1)[0]
        if quality_gate and external_root in QUALITY_GATE_FORBIDDEN_EXTERNAL_IMPORTS:
            failures.append(f"{path}: quality-gate decisions must not import {external_root}")
            continue
        if external_root in FORBIDDEN_EXTERNAL_IMPORTS.get(source, set()):
            failures.append(f"{path}: {source} must not import {external_root}")
            continue
        sdk_owner = VENDOR_SDK_OWNERS.get(external_root)
        if sdk_owner is not None and source != sdk_owner:
            failures.append(f"{path}: {imported} SDK import is restricted to {sdk_owner}")
            continue
        if not imported.startswith("rightjob."):
            continue
        target = imported.split(".", 2)[1]
        if target in STRICTLY_FORBIDDEN.get(source, set()):
            failures.append(f"{path}: {source} must not import {target}")
        elif (
            target in CORE_MODULES
            and target != source
            and target not in ALLOWED_CORE_IMPORTS
            and target not in EXCEPTIONS.get(source, set())
        ):
            failures.append(f"{path}: import published contracts, not rightjob.{target} internals")
    if (
        source
        in {
            "ai_router",
            "executive",
            "planner",
            "provider_adapters",
            "reviewer",
            "validation",
        }
        or quality_gate
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id
                in (
                    FORBIDDEN_ROUTER_CALLS
                    if source == "ai_router" or quality_gate
                    else FORBIDDEN_AI_CALLS
                )
            ):
                failures.append(f"{path}: dynamic execution is prohibited in AI paths")
    return failures


def check_department(path: Path) -> list[str]:
    department = path.relative_to(DEPARTMENTS).parts[0]
    failures: list[str] = []
    for imported in imports(path):
        if imported.startswith("rightjob_departments."):
            target = imported.split(".", 2)[1]
            if target != department:
                failures.append(f"{path}: Department {department} must not import {target}")
        if imported.startswith("rightjob.provider_adapters"):
            failures.append(f"{path}: Departments must not import concrete providers")
        if imported.startswith("rightjob.repositories"):
            failures.append(f"{path}: Departments must not bypass owning repositories")
    return failures


def main() -> int:
    failures: list[str] = []
    for path in CORE.rglob("*.py"):
        failures.extend(check_core(path))
    for path in DEPARTMENTS.rglob("*.py"):
        failures.extend(check_department(path))
    if failures:
        print("\n".join(sorted(failures)))
        return 1
    print("Architecture boundaries: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
