# Migration versions

Phase 1 creates no production tables.

Every future migration must:

1. declare exactly one approved `owner`;
2. live under that module's filename prefix;
3. add non-null `workspace_id` to every tenant-owned table;
4. use tenant-aware composite foreign keys;
5. enable and force PostgreSQL RLS before application access;
6. include cross-tenant denial tests;
7. avoid `pgvector` until its proof gate passes.

