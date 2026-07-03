import { columns, type DataRow } from "../data";

type DataTableProps = {
  title: string;
  rows: DataRow[];
  meta: string;
};

export function DataTable({ title, rows, meta }: DataTableProps) {
  return (
    <div className="data-panel">
      <div className="panel-head">
        <span>{title}</span>
        <span>{meta}</span>
      </div>
      <div className="table-scroll">
        <div className="data-table">
          <div className="table-row table-head">
            <span>#</span>
            {columns.map((column) => (
              <span key={column}>{column}</span>
            ))}
          </div>
          {rows.map((row) => (
            <div className={`table-row ${row.duplicate ? "duplicate-row" : ""}`} key={row.id}>
              <span className="row-id">{row.id}</span>
              {row.cells.map((cell, index) => (
                <span className={`cell cell-${cell.state ?? "clean"}`} key={`${row.id}-${index}`}>
                  {cell.value || "NULL"}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
