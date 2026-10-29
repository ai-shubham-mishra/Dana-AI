"use client";

import { Activity, CheckCircle2, CircleDashed, XCircle, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useJobs } from "@/lib/queries";
import type { JobStatus, JobSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-accent text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
};

const ACTIVE_STATUSES = new Set<JobStatus>(["queued", "running"]);

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

function JobsTable({ jobs }: { jobs: JobSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-5 py-3 font-medium">Job</th>
            <th scope="col" className="px-5 py-3 font-medium">Kind</th>
            <th scope="col" className="px-5 py-3 font-medium">Status</th>
            <th scope="col" className="px-5 py-3 font-medium">Created</th>
            <th scope="col" className="px-5 py-3 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-b border-border last:border-0 hover:bg-muted/50">
              <td className="px-5 py-3 font-medium">{job.title}</td>
              <td className="px-5 py-3 text-muted-foreground">{job.kind}</td>
              <td className="px-5 py-3">
                <StatusBadge status={job.status} />
              </td>
              <td className="px-5 py-3 text-muted-foreground">{relativeTime(job.created_at)}</td>
              <td className="px-5 py-3 text-muted-foreground">{relativeTime(job.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function JobsDashboard() {
  const token = useAccessToken();
  const jobs = useJobs();
  const items = jobs.data ?? [];

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
    body = <JobsTable jobs={items} />;
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
      </div>
    </div>
  );
}
