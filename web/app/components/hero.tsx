import { CopyCommand } from "./copy-command";
import { DataTable } from "./data-table";
import { cleanRows, dirtyRows, reportMetrics } from "../data";

export function Hero() {
  return (
    <section className="hero wrap" id="top">
      <div className="eyebrow">CSV/XLSX data cleaning engine</div>
      <h1>Data Cleaner</h1>
      <p className="hero-lede">Dirty spreadsheets in. Clean files and audit reports out.</p>
      <p className="hero-copy">
        Rinse normalizes dates, emails, phones, casing, duplicates, missing values, and validation
        rules through a deterministic pipeline you can inspect.
      </p>
      <div className="hero-actions">
        <a className="primary-link" href="#objects">
          View report artifact
        </a>
        <CopyCommand />
      </div>
      <div className="comparison-shell">
        <DataTable title="dirty_realistic_customers.csv" rows={dirtyRows} meta="5 rows" />
        <div className="operation-rail">
          <span>operations</span>
          <b>infer</b>
          <b>fill</b>
          <b>normalize</b>
          <b>validate</b>
          <b>dedup</b>
        </div>
        <DataTable title="clean.json" rows={cleanRows} meta="4 rows" />
      </div>
      <div className="metric-strip">
        {reportMetrics.slice(1, 5).map((metric) => (
          <span key={metric.label}>
            <b>{metric.value}</b>
            {metric.label}
          </span>
        ))}
      </div>
    </section>
  );
}
