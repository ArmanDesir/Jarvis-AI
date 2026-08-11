# Department and Capability Standard

## Department standard

A Department is a cohesive business-domain plugin. It owns capabilities and
deterministic rules that naturally change together. Create a new department only
when no existing department owns the domain and separate ownership improves
cohesion. A department is not created merely for a job title, prompt persona,
provider, or workflow step.

A department must publish one manifest, own no duplicate canonical client/project
records, and have no dependency on another department’s internals.

## Capability standard

A Capability is one typed business operation. Before creating one, prove that an
existing capability cannot be extended compatibly without mixing unrelated
responsibilities.

Every capability contract contains:

- capability ID and department ID;
- semantic version and description;
- input and output schemas;
- required permissions and risk classification;
- approval policy;
- required Tool Interfaces;
- required AI capabilities;
- timeout and retry policies;
- idempotency policy;
- cancellation and compensation behavior;
- deterministic validation rules;
- qualitative review criteria;
- emitted versioned events;
- audit and observability requirements;
- cost classification and data sensitivity;
- supported failure modes.

## Execution rules

- Inputs and provider outputs are untrusted until schema validated.
- Domain invariants execute in deterministic capability/domain code.
- A capability asks AI Router for required AI characteristics, never a vendor.
- A capability asks Tool Interfaces for external functions, never an SDK.
- Capabilities cannot coordinate complete workflows or call other departments.
- Results include typed output, evidence, validation status, usage, and normalized
  errors.
- Breaking contract changes require a new major version; running workflows retain
  compatible versions.

## Quality ownership

The capability declares deterministic acceptance checks and optional qualitative
review criteria. Validator executes deterministic checks. Reviewer returns an
assessment. Neither substitutes for Policy or approval.

## Scale requirements

Capabilities declare expected workload, concurrency, provider limits, payload
ceilings, cost class, and whether operations are safe to retry. Unbounded lists,
fan-out, tokens, file sizes, or external calls are prohibited.

## Accepted MVP ownership

The initial Departments are Website, Marketing, and Operations.

- Marketing solely owns brand strategy, brand voice and messaging, visual
  direction, graphic-design briefs, social graphics, website visual assets,
  campaign creative direction, video concepts, and image-generation prompts.
- Website owns website information architecture, UI composition, and
  implementation.
- Operations owns deterministic operational delivery rules. Orchestrator remains
  the sole owner of workflow lifecycle and cross-department coordination.
- Website consumes approved Marketing artifacts through Orchestrator handoffs
  using versioned artifact and Capability contracts.

No duplicate Creative Capability may be registered elsewhere.

## Accepted Reviewer governance

Reviewer emits structured scores, reasons, and evidence. Orchestrator owns
revision execution and durable state. At most two automated revision cycles are
allowed. Two unsuccessful cycles move the workflow to `needs_human_review`;
another revision requires an authorized person or an already-approved workflow
rule.
