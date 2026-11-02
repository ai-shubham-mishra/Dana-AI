"use client";

import { Archive, Boxes, ChevronDown, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Pill, formatWhen, modelHref, normalizeModelName } from "@/components/models-ui";
import { useDeploymentArchive, useDeployments, useModels } from "@/lib/queries";
import type { ArchivedDeployment } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "live" | "idle";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "live", label: "Live" },
  { value: "idle", label: "Idle" },
];

export function ModelsList() {
  const models = useModels();
  const deployments = useDeployments();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const liveByModel = useMemo(() => {
    const counts = new Map<string, number>();
    for (const dep of deployments.data ?? []) {
      if (dep.health.state === "live") counts.set(dep.model_id, (counts.get(dep.model_id) ?? 0) + 1);
    }
    return counts;
  }, [deployments.data]);

  const nameCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const model of models.data ?? []) {
      const key = normalizeModelName(model.name);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [models.data]);

  const all = useMemo(() => models.data ?? [], [models.data]);
  const liveCount = all.filter((model) => (liveByModel.get(model.id) ?? 0) > 0).length;
  const counts: Record<Filter, number> = { all: all.length, live: liveCount, idle: all.length - liveCount };

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return all.filter((model) => {
      const live = (liveByModel.get(model.id) ?? 0) > 0;
      if (filter === "live" && !live) return false;
      if (filter === "idle" && live) return false;
      return !needle || model.name.toLowerCase().includes(needle);
    });
  }, [all, liveByModel, query, filter]);

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-6 md:p-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Models</h1>
          <p className="text-sm text-muted-foreground">
            {all.length} model{all.length === 1 ? "" : "s"} · open one to manage its versions and containers
          </p>
        </div>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative w-full sm:max-w-xs">
          <span className="sr-only">Search models</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search models"
            className="h-9 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40"
          />
        </label>
        <div role="group" aria-label="Filter by status" className="inline-flex w-full rounded-lg border border-border bg-card p-1 sm:w-auto">
          {FILTERS.map((option) => {
            const active = filter === option.value;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(option.value)}
                className={cn(
                  "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors sm:flex-none",
                  active ? "bg-primary text-white shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {option.label}
                <span className={cn("ml-1.5 tabular-nums", active ? "text-white/80" : "text-muted-foreground")}>{counts[option.value]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {models.error ? <p className="text-sm text-destructive">{models.error.message}</p> : null}

      {models.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden>
          {[0, 1, 2].map((key) => (
            <div key={key} className="h-36 animate-pulse rounded-xl border border-border bg-card" />
          ))}
        </div>
      ) : null}

      {!models.isLoading && all.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border p-12 text-center">
          <Boxes className="mb-3 size-8 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">No models yet</p>
          <p className="mt-1 text-sm text-muted-foreground">Finish a training job to create your first model.</p>
        </div>
      ) : null}

      {!models.isLoading && all.length > 0 && visible.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No models match this search or filter.
        </p>
      ) : null}

      {visible.length > 0 ? (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((model) => {
            const live = liveByModel.get(model.id) ?? 0;
            return (
              <li key={model.id}>
                <Link
                  href={modelHref(model, (nameCounts.get(normalizeModelName(model.name)) ?? 0) > 1)}
                  className="group flex h-full flex-col gap-4 rounded-xl border border-border bg-card p-5 outline-none transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-elevated focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="min-w-0 truncate text-base font-semibold group-hover:text-primary">{model.name}</span>
                    {live > 0 ? (
                      <Pill tone="bg-teal/15 text-teal ring-teal/30">
                        <span className="size-1.5 rounded-full bg-teal animate-pulse" aria-hidden />
                        {live} live
                      </Pill>
                    ) : (
                      <Pill tone="bg-muted text-muted-foreground ring-border">Idle</Pill>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded-md bg-muted px-2 py-0.5 font-mono font-medium text-foreground">v{model.latest_version}</span>
                    <span>
                      {model.version_count} version{model.version_count === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="mt-auto text-xs text-muted-foreground">Updated {formatWhen(model.updated_at)}</div>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}

      <ArchiveSection modelNames={new Map(all.map((model) => [model.id, model.name]))} />
    </div>
  );
}

function ArchiveSection({ modelNames }: { modelNames: Map<string, string> }) {
  const archive = useDeploymentArchive();
  const [open, setOpen] = useState(false);
  const items = archive.data ?? [];

  return (
    <section aria-labelledby="archive-heading" className="rounded-xl border border-border bg-card">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 rounded-xl px-5 py-4 text-left outline-none transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        <span className="flex items-center gap-2.5">
          <Archive className="size-4 text-muted-foreground" aria-hidden />
          <span id="archive-heading" className="text-sm font-semibold">
            Container archive
          </span>
          <span className="rounded-md bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">{items.length}</span>
        </span>
        <ChevronDown className={cn("size-4 text-muted-foreground transition-transform duration-200", open && "rotate-180")} aria-hidden />
      </button>

      {open ? (
        <div className="border-t border-border px-5 py-4">
          <p className="mb-4 text-xs text-muted-foreground">
            Deallocated containers are kept here for 7 days, then permanently removed. Only you can see your archive.
          </p>
          {archive.error ? <p className="text-sm text-destructive">{archive.error.message}</p> : null}
          {!archive.error && archive.isLoading ? <div className="h-16 animate-pulse rounded-lg bg-muted" aria-hidden /> : null}
          {!archive.isLoading && !archive.error && items.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing archived.</p>
          ) : null}
          {items.length > 0 ? (
            <ul className="divide-y divide-border">
              {items.map((item) => (
                <ArchiveRow key={item.id} item={item} modelName={modelNames.get(item.model_id) ?? `Model ${item.model_id.slice(0, 8)}`} />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function ArchiveRow({ item, modelName }: { item: ArchivedDeployment; modelName: string }) {
  const days = Math.max(0, Math.min(7, item.days_remaining));
  const urgent = days <= 1;
  return (
    <li className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">
          {modelName} <span className="font-mono text-xs text-muted-foreground">v{item.version}</span>
        </p>
        <p className="mt-0.5 font-mono text-xs text-muted-foreground">{item.container}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Stopped {formatWhen(item.archived_at)}
          {item.created_by_email ? ` · ${item.created_by_email}` : ""}
        </p>
      </div>
      <div className="flex w-full items-center gap-3 sm:w-64">
        <div
          role="meter"
          aria-label="Days until permanent deletion"
          aria-valuemin={0}
          aria-valuemax={7}
          aria-valuenow={days}
          aria-valuetext={`${days} of 7 days remaining`}
          className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={cn("h-full rounded-full transition-all duration-500", urgent ? "bg-destructive" : "bg-primary")}
            style={{ width: `${(days / 7) * 100}%` }}
          />
        </div>
        <span className={cn("shrink-0 whitespace-nowrap text-xs tabular-nums", urgent ? "text-destructive" : "text-muted-foreground")}>
          {days} of 7 days left
        </span>
      </div>
    </li>
  );
}
