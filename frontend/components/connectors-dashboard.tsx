"use client";

import { ChevronLeft, ChevronRight, Database, Table2 } from "lucide-react";
import { useState, type ReactNode } from "react";

import { KeyValueBoxes } from "@/components/key-value";
import { useAccessToken } from "@/lib/auth";
import { useConnectorRows, useConnectors } from "@/lib/queries";
import type { ConnectorPage, ConnectorSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 25;

function formatCount(value: number | null) {
  return value === null ? "Not analyzed" : `~${value.toLocaleString()} rows`;
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

function ConnectorCard({ connector, active, onSelect }: { connector: ConnectorSummary; active: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={cn(
        "flex flex-col gap-3 rounded-xl border bg-card p-4 text-left shadow-sm transition-colors hover:border-primary/40",
        active ? "border-primary ring-1 ring-primary/30" : "border-border",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <Table2 className="size-4 shrink-0 text-primary" aria-hidden />
          <span className="truncate text-sm font-medium">{connector.name}</span>
        </span>
        <span
          className={cn(
            "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
            connector.org_scoped ? "bg-success/15 text-success" : "bg-muted text-muted-foreground",
          )}
        >
          {connector.org_scoped ? "Org scoped" : "Shared"}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatCount(connector.row_estimate)}</span>
        <span>{connector.columns.length} columns</span>
      </div>
    </button>
  );
}

function RowsTable({ data }: { data: ConnectorPage }) {
  if (data.columns.length === 0) {
    return <p className="px-5 py-6 text-sm text-muted-foreground">This table has no columns.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            {data.columns.map((column) => (
              <th key={column.name} scope="col" className="whitespace-nowrap px-5 py-3 font-medium">
                {column.name}
                <span className="ml-1.5 normal-case tracking-normal text-muted-foreground/70">{column.data_type}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.length === 0 ? (
            <tr>
              <td colSpan={data.columns.length} className="px-5 py-6 text-center text-sm text-muted-foreground">
                No rows for your organization yet.
              </td>
            </tr>
          ) : (
            data.rows.map((row, rowIndex) => (
              <tr key={`${data.page}-${rowIndex}`} className="border-b border-border last:border-0 hover:bg-muted/50">
                {row.map((cell, cellIndex) => {
                  const nested = cell !== null && typeof cell === "object";
                  return (
                    <td
                      key={cellIndex}
                      className={cn(
                        "px-5 py-3 align-top text-muted-foreground",
                        nested ? "min-w-48" : "max-w-xs truncate whitespace-nowrap",
                      )}
                    >
                      {nested ? <KeyValueBoxes data={cell} /> : formatCell(cell)}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function RowsPanel({ name }: { name: string }) {
  const [page, setPage] = useState(1);
  const rows = useConnectorRows(name, page, PAGE_SIZE);
  const data = rows.data;
  const totalPages = data?.total_pages ?? 1;

  let body: ReactNode;
  if (rows.isPending) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Loading rows…</p>;
  } else if (rows.error) {
    body = <p className="px-5 py-6 text-sm text-destructive">{rows.error.message}</p>;
  } else if (data) {
    body = <RowsTable data={data} />;
  }

  return (
    <section className="rounded-xl border border-border bg-card shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">{name}</h2>
          {data && !data.org_scoped && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">No org column, showing all rows</span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>
            {data ? `${data.total_rows.toLocaleString()} rows · page ${page} of ${totalPages}` : ""}
          </span>
          <button
            type="button"
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            disabled={page <= 1 || rows.isFetching}
            aria-label="Previous page"
            className="rounded-md border border-border p-1.5 hover:bg-muted disabled:opacity-40"
          >
            <ChevronLeft className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            disabled={!data || page >= totalPages || rows.isFetching}
            aria-label="Next page"
            className="rounded-md border border-border p-1.5 hover:bg-muted disabled:opacity-40"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      </div>
      {body}
    </section>
  );
}

export function ConnectorsDashboard() {
  const token = useAccessToken();
  const connectors = useConnectors();
  const items = connectors.data ?? [];
  const [selected, setSelected] = useState<string | null>(null);

  const activeName = selected ?? items[0]?.name ?? null;

  let body: ReactNode;
  if (!token) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Sign in to see your connectors.</p>;
  } else if (connectors.isPending) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Loading…</p>;
  } else if (connectors.error) {
    body = <p className="px-5 py-6 text-sm text-destructive">{connectors.error.message}</p>;
  } else if (items.length === 0) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">No connectors found in this database.</p>;
  } else {
    body = (
      <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((connector) => (
          <ConnectorCard
            key={connector.name}
            connector={connector}
            active={connector.name === activeName}
            onSelect={() => setSelected(connector.name)}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh min-w-0 flex-1 flex-col">
      <header className="border-b border-border px-6 py-4 md:px-10">
        <h1 className="flex items-center gap-2 text-sm font-semibold">
          <Database className="size-4 text-primary" aria-hidden />
          Connectors
        </h1>
        <p className="text-sm text-muted-foreground">Data connectors available to your organization</p>
      </header>

      <div className="mx-auto w-full max-w-6xl space-y-6 p-6 md:p-10">
        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">Available connectors</h2>
            <span className="text-xs text-muted-foreground">{items.length} total</span>
          </div>
          {body}
        </section>

        {token && activeName && <RowsPanel key={activeName} name={activeName} />}
      </div>
    </div>
  );
}
