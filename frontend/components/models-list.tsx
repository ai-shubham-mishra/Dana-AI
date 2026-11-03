"use client";

import { Boxes, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ArchiveBrowser } from "@/components/archive-browser";
import { Pill, formatWhen, modelHref, normalizeModelName } from "@/components/models-ui";
import { useDeployments, useModels } from "@/lib/queries";
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
  const modelNames = useMemo(() => new Map(all.map((model) => [model.id, model.name])), [all]);
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
        <ArchiveBrowser modelNames={modelNames} />
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
    </div>
  );
}
