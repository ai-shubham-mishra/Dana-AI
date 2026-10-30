"use client";

import { Activity, CheckCircle2, ChevronDown, ChevronUp, CircleDashed, X, XCircle, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from "react";

import { CollapsibleSection } from "@/components/collapsible-section";
import { JobProgressBar, JobTimeline, StatusBadge } from "@/components/job-primitives";
import { KeyValueTree } from "@/components/key-value-tree";
import { useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { isActive } from "@/lib/job-status";
import { useJob, useJobs } from "@/lib/queries";
import type { JobStatus, JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "active" | "succeeded" | "failed";

const FILTERS: Record<Filter, { label: string; matches: (status: JobStatus) => boolean }> = {
  all: { label: "All jobs", matches: () => true },
  active: { label: "Active jobs", matches: isActive },
  succeeded: { label: "Succeeded jobs", matches: (status) => status === "succeeded" },
  failed: { label: "Failed jobs", matches: (status) => status === "failed" },
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
  pressed,
  onPress,
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  tone: string;
  pressed: boolean;
  onPress: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onPress}
      className={cn(
        "rounded-xl border bg-card p-5 text-left shadow-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50",
        pressed ? "border-primary ring-1 ring-primary/30" : "border-border hover:border-foreground/20",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className={cn("size-4", tone)} aria-hidden />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums">{value}</div>
    </button>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: (() => void) | null; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick ?? undefined}
      disabled={!onClick}
      className="inline-flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-3 p-5" aria-hidden>
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="h-10 animate-pulse rounded-md bg-muted" />
      ))}
    </div>
  );
}

function JobsTable({ jobs, selectedId, onSelect }: { jobs: JobSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  function handleRowKey(event: KeyboardEvent<HTMLTableRowElement>, index: number, id: string) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = jobs[index + (event.key === "ArrowDown" ? 1 : -1)];
      if (!next) return;
      onSelect(next.id);
      document.getElementById(`job-row-${next.id}`)?.focus();
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(id);
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-5 py-3 font-medium">Job</th>
            <th scope="col" className="px-5 py-3 font-medium">Job ID</th>
            <th scope="col" className="px-5 py-3 font-medium">Kind</th>
            <th scope="col" className="w-48 px-5 py-3 font-medium">Progress</th>
            <th scope="col" className="px-5 py-3 font-medium">Status</th>
            <th scope="col" className="px-5 py-3 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job, index) => {
            const selected = selectedId === job.id;
            return (
              <tr
                key={job.id}
                id={`job-row-${job.id}`}
                tabIndex={0}
                aria-selected={selected}
                onClick={() => onSelect(job.id)}
                onKeyDown={(event) => handleRowKey(event, index, job.id)}
                className={cn(
                  "cursor-pointer border-b border-border outline-none last:border-0 hover:bg-muted/50 focus-visible:bg-muted/60 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50",
                  selected && "bg-muted/60",
                )}
              >
                <td className="px-5 py-3">
                  <div className="font-medium">{job.title}</div>
                  {job.error ? (
                    <div className="mt-0.5 line-clamp-2 text-xs text-destructive">{job.error}</div>
                  ) : job.message ? (
                    <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{job.message}</div>
                  ) : null}
                </td>
                <td className="px-5 py-3">
                  <span className="block max-w-40 truncate font-mono text-xs text-muted-foreground" title={job.id}>
                    {job.id}
                  </span>
                </td>
                <td className="px-5 py-3 text-muted-foreground">{job.kind}</td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <JobProgressBar percent={job.percent} status={job.status} />
                    <span className="w-9 text-right text-xs tabular-nums text-muted-foreground">{job.percent}%</span>
                  </div>
                </td>
                <td className="px-5 py-3">
                  <StatusBadge status={job.status} />
                </td>
                <td className="px-5 py-3 text-muted-foreground">{relativeTime(job.updated_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function JobBlade({
  jobId,
  position,
  total,
  onPrev,
  onNext,
  onClose,
}: {
  jobId: string;
  position: number | null;
  total: number;
  onPrev: (() => void) | null;
  onNext: (() => void) | null;
  onClose: () => void;
}) {
  const job = useJob(jobId);
  const detail = job.data;
  const paramCount = Object.keys(detail?.params ?? {}).length;
  const metricCount = Object.keys(detail?.metrics ?? {}).length;
  const stageLine = detail ? [detail.stage?.replace(/_/g, " "), detail.message].filter(Boolean).join(" · ") : "";

  return (
    <aside
      aria-label="Job details"
      className="fixed inset-x-0 bottom-0 z-40 flex max-h-[85dvh] flex-col overflow-hidden rounded-t-2xl border-t border-border bg-card shadow-2xl lg:sticky lg:top-6 lg:z-0 lg:max-h-[calc(100dvh-3rem)] lg:rounded-xl lg:border lg:shadow-sm"
    >
      <header className="flex items-center gap-1 border-b border-border px-4 py-2.5">
        <p className="min-w-0 flex-1 text-xs text-muted-foreground">
          {position !== null ? `Job ${position} of ${total}` : "Job details"}
        </p>
        <IconButton label="Previous job" onClick={onPrev}>
          <ChevronUp className="size-4" aria-hidden />
        </IconButton>
        <IconButton label="Next job" onClick={onNext}>
          <ChevronDown className="size-4" aria-hidden />
        </IconButton>
        <IconButton label="Close job details" onClick={onClose}>
          <X className="size-4" aria-hidden />
        </IconButton>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {job.isPending ? <p className="text-sm text-muted-foreground">Loading job…</p> : null}
        {job.error ? <p className="text-sm text-destructive">{job.error.message}</p> : null}
        {detail ? (
          <div className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-3">
                <h3 className="min-w-0 text-base font-semibold leading-snug">{detail.title}</h3>
                <StatusBadge status={detail.status} />
              </div>
              <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                <span className="min-w-0 truncate">{stageLine}</span>
                <span className="shrink-0 text-sm font-semibold tabular-nums text-foreground">{detail.percent}%</span>
              </div>
              <JobProgressBar percent={detail.percent} status={detail.status} />
              {detail.error ? <p className="rounded-md bg-destructive/10 p-2 text-xs text-destructive">{detail.error}</p> : null}
            </div>

            <CollapsibleSection title="Progress updates" count={detail.events.length}>
              {detail.events.length > 0 ? (
                <JobTimeline events={detail.events} status={detail.status} percent={detail.percent} />
              ) : (
                <p className="text-sm text-muted-foreground">No updates yet.</p>
              )}
            </CollapsibleSection>

            {paramCount > 0 ? (
              <CollapsibleSection title="Parameters" count={paramCount} defaultOpen={false}>
                <KeyValueTree data={detail.params} />
              </CollapsibleSection>
            ) : null}

            {metricCount > 0 ? (
              <CollapsibleSection title="Metrics" count={metricCount} defaultOpen={false}>
                <KeyValueTree data={detail.metrics} />
              </CollapsibleSection>
            ) : null}

            {detail.artifact ? (
              <CollapsibleSection title="Artifact" defaultOpen={false}>
                <p className="text-sm">
                  {detail.artifact.name} <span className="text-muted-foreground">({formatBytes(detail.artifact.bytes)})</span>
                </p>
              </CollapsibleSection>
            ) : null}
          </div>
        ) : null}
      </div>
    </aside>
  );
}

export function JobsDashboard() {
  const token = useAccessToken();
  const jobs = useJobs();
  const items = useMemo(() => jobs.data ?? [], [jobs.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  const visible = useMemo(() => items.filter((job) => FILTERS[filter].matches(job.status)), [items, filter]);
  const countOf = (predicate: (status: JobStatus) => boolean) => items.filter((job) => predicate(job.status)).length;
  const selectedIndex = visible.findIndex((job) => job.id === selectedId);
  const goTo = (offset: number) => {
    const target = visible[selectedIndex + offset];
    if (target) setSelectedId(target.id);
  };

  useEffect(() => {
    if (!selectedId) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId]);

  let body: ReactNode;
  if (!token) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Sign in to see your jobs.</p>;
  } else if (jobs.isPending) {
    body = <TableSkeleton />;
  } else if (jobs.error) {
    body = <p className="px-5 py-6 text-sm text-destructive">{jobs.error.message}</p>;
  } else if (items.length === 0) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">No training jobs yet.</p>;
  } else if (visible.length === 0) {
    body = (
      <div className="flex flex-col items-start gap-2 px-5 py-6 text-sm text-muted-foreground">
        <span>No jobs match this filter.</span>
        <button type="button" onClick={() => setFilter("all")} className="text-xs font-medium text-primary hover:underline">
          Show all jobs
        </button>
      </div>
    );
  } else {
    body = <JobsTable jobs={visible} selectedId={selectedId} onSelect={setSelectedId} />;
  }

  return (
    <div className="flex min-h-dvh min-w-0 flex-1 flex-col">
      <header className="border-b border-border px-6 py-4 md:px-10">
        <h1 className="text-sm font-semibold">Jobs</h1>
        <p className="text-sm text-muted-foreground">Training runs for your organization</p>
      </header>

      <div className="mx-auto w-full max-w-7xl space-y-6 p-6 md:p-10">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Total jobs"
            value={items.length}
            icon={CircleDashed}
            tone="text-muted-foreground"
            pressed={filter === "all"}
            onPress={() => setFilter("all")}
          />
          <StatCard
            label="Active"
            value={countOf(isActive)}
            icon={Activity}
            tone="text-primary"
            pressed={filter === "active"}
            onPress={() => setFilter("active")}
          />
          <StatCard
            label="Succeeded"
            value={countOf((status) => status === "succeeded")}
            icon={CheckCircle2}
            tone="text-success"
            pressed={filter === "succeeded"}
            onPress={() => setFilter("succeeded")}
          />
          <StatCard
            label="Failed"
            value={countOf((status) => status === "failed")}
            icon={XCircle}
            tone="text-destructive"
            pressed={filter === "failed"}
            onPress={() => setFilter("failed")}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_26rem] lg:items-start">
          <section className="min-w-0 rounded-xl border border-border bg-card shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">{FILTERS[filter].label}</h2>
              <span className="text-xs tabular-nums text-muted-foreground">
                {visible.length} of {items.length}
              </span>
            </div>
            {body}
          </section>

          {selectedId ? (
            <JobBlade
              key={selectedId}
              jobId={selectedId}
              position={selectedIndex >= 0 ? selectedIndex + 1 : null}
              total={visible.length}
              onPrev={selectedIndex > 0 ? () => goTo(-1) : null}
              onNext={selectedIndex >= 0 && selectedIndex < visible.length - 1 ? () => goTo(1) : null}
              onClose={() => setSelectedId(null)}
            />
          ) : (
            <aside className="hidden min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground lg:flex lg:sticky lg:top-6">
              Select a job to see its progress, parameters and metrics.
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
