import { ArrowUpRight, Download } from "lucide-react";

export function FinalCta() {
  return (
    <section className="wrap final-cta">
      <div>
        <span>CLI, API, and web surface</span>
        <h2>Use the sample run as the contract.</h2>
        <p>
          Rinse keeps the workflow product-specific: dirty file, selected operations,
          clean export, and audit report. That is the value. Everything else is noise.
        </p>
      </div>
      <div className="cta-actions">
        <a href="https://github.com/Hqzdev/Rinse">
          <ArrowUpRight size={16} />
          <span>View repository</span>
        </a>
        <a href="/expected_realistic_customers_report.json">
          <Download size={16} />
          <span>Sample report</span>
        </a>
      </div>
    </section>
  );
}
