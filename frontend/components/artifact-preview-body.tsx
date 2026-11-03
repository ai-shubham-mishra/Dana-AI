"use client";

import { Highlight, themes } from "prism-react-renderer";
import { useEffect, useState } from "react";

import { PREVIEW_MAX_ROWS, type ArtifactPreview, type CodeLanguage, type TablePreview } from "@/lib/artifact-preview";
import { cn } from "@/lib/utils";

function useIsDark() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setDark(root.classList.contains("dark"));
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

function CodeView({ text, language }: { text: string; language: CodeLanguage }) {
  const theme = useIsDark() ? themes.nightOwl : themes.github;
  return (
    <Highlight theme={theme} code={text.replace(/\n$/, "")} language={language}>
      {({ tokens, getTokenProps, style }) => (
        <div className="min-h-0 flex-1 overflow-auto" style={style}>
          <div className="min-w-max p-4 font-mono text-xs leading-relaxed">
            {tokens.map((line, i) => (
              <div key={i} className="flex">
                <span className="w-10 shrink-0 select-none pr-4 text-right tabular-nums opacity-50">{i + 1}</span>
                <span className="whitespace-pre">
                  {line.length === 0
                    ? " "
                    : line.map((token, key) => <span key={key} {...getTokenProps({ token, key })} />)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Highlight>
  );
}

function TextView({ text }: { text: string }) {
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <pre className="whitespace-pre p-5 font-mono text-xs leading-relaxed">{text}</pre>
    </div>
  );
}

function TableView({ table }: { table: TablePreview }) {
  if (table.width === 0) {
    return <p className="p-5 text-sm text-muted-foreground">This file has no rows.</p>;
  }
  const hidden = table.totalRows - table.rows.length;
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-max min-w-full border-separate border-spacing-0 font-mono text-xs">
          <thead className="sticky top-0 z-10 bg-muted">
            <tr>
              {table.headers.map((header, i) => (
                <th key={i} className="whitespace-nowrap border-b border-r border-border px-3 py-2 text-left font-semibold">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, r) => (
              <tr key={r} className="odd:bg-card even:bg-muted/30 hover:bg-accent/40">
                {row.map((cell, c) => (
                  <td key={c} className="whitespace-nowrap border-b border-r border-border px-3 py-1.5">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-border bg-card px-5 py-2 text-xs tabular-nums text-muted-foreground">
        {hidden > 0
          ? `Showing first ${PREVIEW_MAX_ROWS.toLocaleString()} of ${table.totalRows.toLocaleString()} rows`
          : `${table.totalRows.toLocaleString()} ${table.totalRows === 1 ? "row" : "rows"}`}
      </p>
    </div>
  );
}

function SheetsView({ sheets }: { sheets: { name: string; table: TablePreview }[] }) {
  const [active, setActive] = useState(0);
  if (sheets.length === 0) {
    return <p className="p-5 text-sm text-muted-foreground">This workbook has no sheets.</p>;
  }
  const current = sheets[Math.min(active, sheets.length - 1)];
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {sheets.length > 1 && (
        <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-border bg-card px-3 pt-2">
          {sheets.map((sheet, i) => (
            <button
              key={`${sheet.name}-${i}`}
              type="button"
              role="tab"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={cn(
                "whitespace-nowrap rounded-t-md border border-b-0 px-3 py-1.5 text-xs",
                i === active
                  ? "border-border bg-background font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:bg-muted",
              )}
            >
              {sheet.name}
            </button>
          ))}
        </div>
      )}
      <TableView table={current.table} />
    </div>
  );
}

export function ArtifactPreviewBody({ preview }: { preview: ArtifactPreview }) {
  switch (preview.kind) {
    case "code":
      return <CodeView text={preview.text} language={preview.language} />;
    case "text":
      return <TextView text={preview.text} />;
    case "table":
      return <TableView table={preview.table} />;
    case "sheets":
      return <SheetsView sheets={preview.sheets} />;
  }
}
