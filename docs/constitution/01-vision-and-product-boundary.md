# Vision and Product Boundary

## Mission

Rightjob AI OS is a multi-tenant agency operating system controlled through one
user-facing Executive AI. It converts goals into governed, observable work
performed by dynamically selected department capabilities.

It is not a chatbot, an unconstrained autonomous-agent network, or a replacement
for every external agency platform.

## Product promises

- One coherent user relationship through the Executive.
- Durable context across clients, projects, tasks, decisions, and conversations.
- Only required departments are activated for a request.
- Every consequential action is authorized, traceable, and recoverable where
  technically possible.
- Departments, tools, and providers are replaceable behind contracts.
- Tenant data is isolated at every boundary.

## MVP boundary

The proposed initial domains are Website, Marketing, and Operations. Final scope
and the ownership of creative capabilities require owner approval.

The MVP includes conversation, context resolution, typed planning, durable
orchestration, policy/approval, memory, audit, and representative workflows. It
does not include a no-code workflow builder, third-party executable plugin
marketplace, proprietary model training, or autonomous financial/contract
execution.

## Scale boundary

Every feature must be credible for at least 1,000 agencies under documented
workload assumptions. The architecture target is 10,000 workspaces without
changing domain boundaries. This does not require premature distributed systems;
it requires tenant isolation, bounded work, backpressure, quotas, stateless
horizontal scaling, durable state, and measurable capacity.

## Simplicity boundary

The default is a modular monolith with independently scalable processes. New
services or infrastructure require a verified requirement, proof that existing
components cannot satisfy it, operational/security cost analysis, migration
impact, and simpler alternatives.

Microservices, Kafka, a separate vector database, multi-region active-active, and
an executable plugin marketplace are constitutionally deferred until an approved
ADR provides measurements.
