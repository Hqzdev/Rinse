import { AlertTriangle, CheckCircle2, FileJson, GitBranch, Table2 } from "lucide-react";
import type { CSSProperties } from "react";
import { cleanRows, dirtyRows, pipelineSteps, reportIssues, reportMetrics } from "../data";
import { DataTable } from "./data-table";

export function ObjectBlocks() {
  return (
    <section className="wrap object-section" id="objects">
      <DatasetSpecimen />
      <PipelineInstrument />
      <ReportArtifact />
    </section>
  );
}

function DatasetSpecimen() {
  return (
    <div className="object-block">
      <div className="object-copy">
        <span>Object 01</span>
        <h2>Dirty dataset specimen</h2>
        <p>
          The sample file contains duplicate customers, mixed date formats, missing values,
          broken emails, invalid phone data, and status values that should not pass validation.
        </p>
      </div>
      <div className="object-surface">
        <div className="mini-label">
          <Table2 size={15} />
          <span>Hover reveals the damaged cells</span>
        </div>
        <DataTable title="incoming workbook" rows={dirtyRows} meta="CSV + XLSX" />
      </div>
    </div>
  );
}

function PipelineInstrument() {
  return (
    <div className="object-block">
      <div className="object-copy">
        <span>Object 02</span>
        <h2>Cleaning pipeline instrument</h2>
        <p>
          Each operation returns a structured result. The report is built from those results,
          so CLI, API, and web UI explain the same run without rewriting logic.
        </p>
      </div>
      <div className="pipeline-card">
        <div className="mini-label">
          <GitBranch size={15} />
          <span>deterministic operation order</span>
        </div>
        <div className="pipeline-line">
          {pipelineSteps.map((step, index) => (
            <div
              className="pipeline-step"
              key={step.name}
              style={{ "--step": index } as CSSProperties & Record<"--step", number>}
            >
              <span>{step.name}</span>
              <b>{step.count}</b>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReportArtifact() {
  return (
    <div className="object-block">
      <div className="object-copy">
        <span>Object 03</span>
        <h2>Report/output artifact</h2>
        <p>
          Rinse exports clean records and a machine-readable audit report. The website frames
          that report as the product's proof, not as decoration.
        </p>
      </div>
      <div className="report-card" id="output">
        <div className="report-head">
          <div>
            <FileJson size={16} />
            <span>expected_realistic_customers_report.json</span>
          </div>
          <b>golden snapshot</b>
        </div>
        <div className="report-metrics">
          {reportMetrics.map((metric) => (
            <div className={`report-metric tone-${metric.tone ?? "neutral"}`} key={metric.label}>
              <span>{metric.label}</span>
              <b>{metric.value}</b>
            </div>
          ))}
        </div>
        <div className="report-issues">
          {reportIssues.map((issue) => (
            <div className="issue-row" key={`${issue.row}-${issue.rule}`}>
              <AlertTriangle size={14} />
              <span>{issue.row}</span>
              <b>{issue.rule}</b>
              <code>{issue.value}</code>
            </div>
          ))}
        </div>
        <div className="clean-preview">
          <div className="mini-label">
            <CheckCircle2 size={15} />
            <span>clean output remains inspectable</span>
          </div>
          <DataTable title="clean records" rows={cleanRows} meta="JSON export" />
        </div>
      </div>
    </div>
  );
}
