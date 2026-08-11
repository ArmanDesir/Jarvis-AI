# Contribution rules

1. Read the Constitution, relevant ADRs, contracts, and module guidance.
2. Complete the Architecture Review Checklist for material work.
3. Change only the owning module and its published contracts.
4. Never import another module's internals or tables.
5. Add one deterministic test for non-trivial behavior.
6. Run `make ci`.
7. Do not weaken security, tenant isolation, policy, audit, or provider
   replaceability to make a test pass.

New infrastructure, services, ownership changes, providers, Departments, or
Constitution exceptions require the approved architecture process. Phase 2 may
not begin without separate instruction.

