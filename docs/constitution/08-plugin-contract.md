# Plugin Contract

## Scope

Every Department is delivered as a plugin. In MVP, executable plugins are trusted
first-party packages released through the controlled build pipeline. Uploading
third-party executable code is prohibited.

## Allowed dependencies

Plugins may depend only on:

- the versioned Plugin SDK;
- published capability, tool, event, and shared value contracts;
- standard/runtime libraries approved by dependency policy.

Plugins cannot import API internals, Orchestrator internals, repositories or ORM
models from another module, another plugin, provider SDKs, or deployment code.

## Required manifest

The immutable, versioned manifest declares department identity, capabilities,
schemas, permissions, risks, approval requirements, tool/AI requirements,
events, compatibility, configuration schema, data sensitivity, and checksum.
Activation and version pinning are workspace-scoped Registry responsibilities.

The manifest contains logical handler identifiers resolved by the composition
root; it cannot contain arbitrary executable expressions, URLs, secrets, or
database connection information.

## Runtime contract

The SDK supplies a typed invocation context: workspace, actor, correlation,
deadline, cancellation, policy decision reference, approved secret references,
idempotency scope, and observability sink. It exposes no unrestricted database,
network, subprocess, filesystem, or code-execution handle.

Results use a standard envelope with output schema version, evidence, emitted
events, usage, cost, warnings, and normalized failure.

## Isolation

Trusted first-party plugins may share a process while boundary tests and
least-privilege runtime credentials are enforced. A future untrusted plugin
model requires a separate approved threat model, sandbox/process boundary,
package signing, network/secret policy, revocation, and incident controls.

MVP permits trusted first-party Department plugins only. Configuration-only
integrations and provider adapters are not Department plugins, but remain
subject to Tool, Adapter, credential, Policy, tenancy, and audit boundaries.
Any future executable-plugin system additionally requires permission manifests,
tenant-scoped credentials, network restrictions, resource quotas, dependency
scanning, compatibility governance, and emergency disabling.

## Compatibility and removal

Contract tests must run against every supported plugin version. Removal requires
evidence that no active workspace or workflow is pinned to it, or a tested
migration. A plugin cannot silently replace another plugin’s capability owner.
