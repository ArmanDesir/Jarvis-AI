# Database ownership

PostgreSQL is shared infrastructure, not a shared domain. Each schema object and
migration has exactly one module owner. The migration runner is centralized only
for ordering and deployment safety.

Migration filenames use `<owner>_<revision>_<description>.py`. CI rejects
unassigned ownership and tenant-table creation without direct RLS scaffolding.

