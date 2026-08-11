"""Static safety checks for module-owned PostgreSQL migrations."""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "db/migrations/versions"


def main() -> int:
    failures: list[str] = []
    for path in VERSIONS.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        declarations: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {
                    "tenant_tables",
                    "tenant_scope_exceptions",
                }:
                    declarations[target.id] = ast.literal_eval(node.value)
        if not re.search(r'^owner\s*=\s*"[a-z_]+"', text, re.MULTILINE):
            failures.append(f"{path}: migration must declare one lowercase module owner")
        if "op.create_table(" in text:
            created = set(re.findall(r'op\.create_table\(\s*"([a-z_]+)"', text))
            tenant_tables = declarations.get("tenant_tables", set())
            exceptions = declarations.get("tenant_scope_exceptions", {})
            if not isinstance(tenant_tables, set) or not isinstance(exceptions, dict):
                failures.append(f"{path}: migration table classifications must be literals")
                continue
            unclassified = created - tenant_tables - set(exceptions)
            if unclassified:
                failures.append(f"{path}: unclassified tables: {sorted(unclassified)}")
            for table in tenant_tables:
                if table not in created:
                    failures.append(f"{path}: classified tenant table not created: {table}")
                if '"workspace_id"' not in text:
                    failures.append(f"{path}: tenant table requires workspace_id")
                if f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" not in text:
                    failures.append(f"{path}: {table} requires enabled RLS")
                if f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" not in text:
                    failures.append(f"{path}: {table} requires forced RLS")
        if "vector(" in text.lower() or "create extension vector" in text.lower():
            failures.append(
                f"{path}: pgvector is proof-gated and unavailable for production migrations"
            )
    if failures:
        print("\n".join(failures))
        return 1
    print("Migration safety: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
