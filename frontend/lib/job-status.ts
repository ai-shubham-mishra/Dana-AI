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

// Brand path: cream (0%) → purple (50%) → green (100%). Failures are red.
const PROGRESS_GRADIENT = "linear-gradient(90deg, var(--background) 0%, var(--primary) 50%, var(--success) 100%)";

export function progressFill(status: JobStatus): string {
  if (status === "failed") return "var(--destructive)";
  if (status === "cancelled") return "var(--muted-foreground)";
  return PROGRESS_GRADIENT;
}

// Colour for a single percentage along the cream → purple → green path.
export function percentColor(percent: number): string {
  const value = Math.min(100, Math.max(0, percent));
  if (value <= 50) return `color-mix(in srgb, var(--primary) ${value * 2}%, var(--background))`;
  return `color-mix(in srgb, var(--success) ${(value - 50) * 2}%, var(--primary))`;
}

export function progressStageColor(status: JobStatus, percent: number): string {
  if (status === "failed") return "var(--destructive)";
  if (status === "succeeded") return "var(--success)";
  if (status === "cancelled") return "var(--muted-foreground)";
  return percentColor(percent);
}
