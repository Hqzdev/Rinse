import { architectureLayers } from "../data";

export function ArchitectureSection() {
  return (
    <section className="wrap architecture-section" id="architecture">
      <div className="section-heading">
        <span>Architecture</span>
        <h2>Not a loose pandas script.</h2>
        <p>
          The product starts with a hexagonal core. Interfaces can change without rewriting
          the cleaning engine.
        </p>
      </div>
      <div className="architecture-grid">
        {architectureLayers.map((layer) => (
          <article className="architecture-layer" key={layer.title}>
            <h3>{layer.title}</h3>
            <p>{layer.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
