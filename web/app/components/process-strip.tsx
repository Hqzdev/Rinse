import { processSteps } from "../data";

export function ProcessStrip() {
  return (
    <section className="wrap process-section" id="method">
      <div className="section-heading">
        <span>Method</span>
        <h2>One pipeline, three visible outcomes.</h2>
      </div>
      <div className="process-grid">
        {processSteps.map((step) => (
          <article className="process-step" key={step.index}>
            <span>{step.index}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
