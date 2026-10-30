"use client";

import { motion } from "framer-motion";
import { Activity, CheckCircle2, CircleDashed, XCircle, type LucideIcon } from "lucide-react";
import { useState, type ReactNode } from "react";

import { KeyValueBoxes } from "@/components/key-value";
import { useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useJob, useJobs } from "@/lib/queries";
import type { JobEvent, JobStatus, JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-accent text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
};

const ACTIVE_STATUSES = new Set<JobStatus>(["queued", "running"]);

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ProgressBar({ percent, status }: { percent: number; status: JobStatus }) {
  const tone = status === "failed" ? "bg-destructive" : status === "succeeded" ? "bg-success" : "bg-primary";
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-full rounded-full transition-[width] duration-500", tone)} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}


function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}

function StatCard({ label, value, icon: Icon, tone }: { label: string; value: number; icon: LucideIcon; tone: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className={cn("size-4", tone)} aria-hidden />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function JobsTable({ jobs, selectedId, onSelect }: { jobs: JobSummary[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-5 py-3 font-medium">Job</th>
            <th scope="col" className="px-5 py-3 font-medium">Kind</th>
            <th scope="col" className="w-56 px-5 py-3 font-medium">Progress</th>
            <th scope="col" className="px-5 py-3 font-medium">Status</th>
            <th scope="col" className="px-5 py-3 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr
              key={job.id}
              onClick={() => onSelect(job.id)}
              aria-selected={selectedId === job.id}
              className={cn(
                "cursor-pointer border-b border-border last:border-0 hover:bg-muted/50",
                selectedId === job.id && "bg-muted/60",
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
              <td className="px-5 py-3 text-muted-foreground">{job.kind}</td>
              <td className="px-5 py-3">
                <div className="flex items-center gap-2">
                  <ProgressBar percent={job.percent} status={job.status} />
                  <span className="w-9 text-right text-xs tabular-nums text-muted-foreground">{job.percent}%</span>
                </div>
              </td>
              <td className="px-5 py-3">
                <StatusBadge status={job.status} />
              </td>
              <td className="px-5 py-3 text-muted-foreground">{relativeTime(job.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Timeline({ events, status }: { events: JobEvent[]; status: JobStatus }) {
  const live = ACTIVE_STATUSES.has(status);
  const last = events.length - 1;
  const endDot = status === "failed" ? "bg-destructive" : status === "succeeded" ? "bg-success" : "bg-primary";

  return (
    <ol className="space-y-2 border-l border-border pl-4">
      {events.map((event, index) => {
        const isLatest = index === last;
        return (
          <motion.li
            key={`${event.created_at}-${index}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className={cn("relative text-sm transition-colors duration-500", !isLatest && "text-muted-foreground")}
          >
            <span className="absolute -left-[21px] top-1.5 flex size-2 items-center justify-center" aria-hidden>
              {isLatest && live ? (
                <motion.span
                  className="absolute inline-flex size-2 rounded-full bg-primary"
                  animate={{ scale: [1, 2.2, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                />
              ) : null}
              <span
                className={cn(
                  "relative inline-flex size-2 rounded-full transition-colors duration-500",
                  isLatest ? endDot : "bg-muted-foreground/40",
                )}
              />
            </span>
            <span className="text-xs tabular-nums text-muted-foreground">{event.percent}%</span>{" "}
            <span className={cn(isLatest && "font-medium")}>{event.message}</span>
          </motion.li>
        );
      })}
    </ol>
  );
}

function JobDetailPanel({ jobId }: { jobId: string }) {
  const job = useJob(jobId);
  if (job.isPending) return <p className="px-5 py-6 text-sm text-muted-foreground">Loading job…</p>;
  if (job.error) return <p className="px-5 py-6 text-sm text-destructive">{job.error.message}</p>;
  const detail = job.data;
  if (!detail) return null;
  const params = Object.entries(detail.params ?? {});
  const metrics = Object.entries(detail.metrics ?? {});

  return (
    <div className="space-y-6 p-5">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">{detail.title}</h3>
          <StatusBadge status={detail.status} />
        </div>
        <ProgressBar percent={detail.percent} status={detail.status} />
        <p className="text-xs text-muted-foreground">
          {detail.stage ? <span className="capitalize">{detail.stage.replace(/_/g, " ")}</span> : null}
          {detail.stage && detail.message ? " · " : null}
          {detail.message}
        </p>
        {detail.error ? <p className="text-xs text-destructive">{detail.error}</p> : null}
      </div>

      {params.length > 0 ? (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Parameters</h4>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
            {params.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="min-w-0 font-mono text-xs leading-5">
                  <KeyValueBoxes data={value} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {metrics.length > 0 ? (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Metrics</h4>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
            {metrics.map(([key, value]) => (
              <div key={key} className="contents">
                <dt className="text-muted-foreground">{key}</dt>
                <dd className="min-w-0 font-mono text-xs leading-5">
                  <KeyValueBoxes data={value} />
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {detail.artifact ? (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Artifact</h4>
          <p className="text-sm">
            {detail.artifact.name} <span className="text-muted-foreground">({formatBytes(detail.artifact.bytes)})</span>
          </p>
        </section>
      ) : null}

      {detail.events.length > 0 ? (
        <section className="space-y-2">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Timeline</h4>
          <Timeline events={detail.events} status={detail.status} />
        </section>
      ) : null}
    </div>
  );
}


export function JobsDashboard() {
  const token = useAccessToken();
  const jobs = useJobs();
  const items = jobs.data ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const count = (predicate: (status: JobStatus) => boolean) => items.filter((job) => predicate(job.status)).length;
  const active = count((status) => ACTIVE_STATUSES.has(status));
  const succeeded = count((status) => status === "succeeded");
  const failed = count((status) => status === "failed");

  let body: ReactNode;
  if (!token) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Sign in to see your jobs.</p>;
  } else if (jobs.isPending) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">Loading…</p>;
  } else if (jobs.error) {
    body = <p className="px-5 py-6 text-sm text-destructive">{jobs.error.message}</p>;
  } else if (items.length === 0) {
    body = <p className="px-5 py-6 text-sm text-muted-foreground">No training jobs yet.</p>;
  } else {
    body = <JobsTable jobs={items} selectedId={selectedId} onSelect={(id) => setSelectedId((current) => (current === id ? null : id))} />;
  }

  return (
    <div className="flex min-h-dvh min-w-0 flex-1 flex-col">
      <header className="border-b border-border px-6 py-4 md:px-10">
        <h1 className="text-sm font-semibold">Jobs</h1>
        <p className="text-sm text-muted-foreground">Training runs for your organization</p>
      </header>

      <div className="mx-auto w-full max-w-5xl space-y-6 p-6 md:p-10">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Total jobs" value={items.length} icon={CircleDashed} tone="text-muted-foreground" />
          <StatCard label="Active" value={active} icon={Activity} tone="text-primary" />
          <StatCard label="Succeeded" value={succeeded} icon={CheckCircle2} tone="text-success" />
          <StatCard label="Failed" value={failed} icon={XCircle} tone="text-destructive" />
        </div>

        <section className="rounded-xl border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <h2 className="text-sm font-semibold">All jobs</h2>
            <span className="text-xs text-muted-foreground">{items.length} total</span>
          </div>
          {body}
        </section>

        {selectedId ? (
          <section className="rounded-xl border border-border bg-card shadow-sm">
            <div className="flex items-center justify-between border-b border-border px-5 py-3">
              <h2 className="text-sm font-semibold">Job details</h2>
              <button type="button" onClick={() => setSelectedId(null)} className="text-xs text-muted-foreground hover:text-foreground">
                Close
              </button>
            </div>
            <JobDetailPanel jobId={selectedId} />
          </section>
        ) : null}
      </div>
    </div>
  );
}
