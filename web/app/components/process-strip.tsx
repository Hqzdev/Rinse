import { processSteps } from "../data";
import type { CSSProperties } from "react";

export function ProcessStrip() {
  return (
    <section className="wrap process-section" id="method">
      <div className="section-heading">
        <span>Method</span>
        <h2>One pipeline, three visible outcomes.</h2>
      </div>
      <div className="process-grid">
        {processSteps.map((step, index) => (
          <article
            className="process-step"
            key={step.index}
            style={{ "--step": index } as CSSProperties & Record<"--step", number>}
          >
            <span>{step.index}</span>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
