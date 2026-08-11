# Architecture boundary guidance

`scripts/check_architecture.py` parses Python imports without third-party
dependencies.

It enforces:

- core modules cannot import another module's internal package;
- Provider Adapters may depend on Tool Interfaces;
- Tool Interfaces cannot depend on Provider Adapters;
- Executive, Planner, Reviewer, and Memory have stricter prohibited edges;
- Departments cannot import another Department;
- Departments cannot import concrete providers or shared Repository shortcuts.

`scripts/check_migrations.py` rejects unowned migrations, tenant-table creation
without `workspace_id` and forced RLS scaffolding, and production `pgvector`
migrations.

Static checks do not prove runtime tenant isolation. Real PostgreSQL RLS and
cross-tenant denial tests become mandatory with the first tenant-owned table.

