import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  /** Plain-language summary; read by screen readers in place of the chart graphic. */
  summary: string;
  /** The same numbers as a table, for anyone who cannot use the chart. */
  table: { columns: string[]; rows: (string | number)[][] };
  children: ReactNode;
  className?: string;
}

export default function ChartCard({ title, summary, table, children, className = "" }: ChartCardProps) {
  return (
    <figure className={`min-w-0 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5 ${className}`}>
      <figcaption>
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-sm text-slate-600">{summary}</p>
      </figcaption>
      <div role="img" aria-label={`${title}. ${summary}`} className="mt-4 h-64 w-full">
        {children}
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-brand-600">Show data table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                {table.columns.map((c) => (
                  <th key={c} scope="col" className="py-1 pr-4 font-medium">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0">
                  {row.map((cell, j) => (j === 0 ? (
                    <th key={j} scope="row" className="py-1 pr-4 font-normal text-slate-700">{cell}</th>
                  ) : (
                    <td key={j} className="py-1 pr-4 tabular-nums">{cell}</td>
                  )))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
