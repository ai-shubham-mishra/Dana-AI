import type { JobStatus } from "@/lib/types";

export const ACTIVE_STATUSES = new Set<JobStatus>(["queued", "running"]);

export const STATUS_STYLES: Record<JobStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-accent text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
};

export function isActive(status: JobStatus): boolean {
  return ACTIVE_STATUSES.has(status);
}

// Light brand purple at 0%, purple while running, green on success, red on failure.
export function progressTone(status: JobStatus, percent: number): string {
  if (status === "failed") return "bg-destructive";
  if (status === "succeeded") return "bg-success";
  if (status === "cancelled") return "bg-muted-foreground";
  return percent > 0 ? "bg-primary" : "bg-brand-purple";
}
