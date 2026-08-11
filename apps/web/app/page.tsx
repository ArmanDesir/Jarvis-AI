const proofGates = [
  ["Temporal", "Not started"],
  ["Clerk", "Not started"],
  ["pgvector", "Not started"],
] as const;

export default function SystemStatusPage() {
  return (
    <main id="main">
      <p className="eyebrow">Engineering foundation</p>
      <h1>Rightjob AI OS is ready for local development.</h1>
      <p className="lede">
        This Phase 1 shell exposes system status only. Business capabilities,
        AI, workflows, and external effects are intentionally unavailable.
      </p>

      <section aria-labelledby="runtime-heading">
        <h2 id="runtime-heading">Runtime status</h2>
        <dl className="status-grid">
          <div>
            <dt>Frontend</dt>
            <dd>
              <span className="indicator" aria-hidden="true" /> Running
            </dd>
          </div>
          <div>
            <dt>API</dt>
            <dd>
              Check <code>/health</code> on the configured API process
            </dd>
          </div>
          <div>
            <dt>Worker</dt>
            <dd>Idle by design</dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby="proof-heading">
        <h2 id="proof-heading">Proof-gate technologies</h2>
        <ul>
          {proofGates.map(([name, state]) => (
            <li key={name}>
              <strong>{name}</strong>
              <span>{state}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
