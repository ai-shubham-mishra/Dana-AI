import type { DeploymentHealthState, ModelSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export const HEALTH_STYLE: Record<string, string> = {
  live: "bg-teal/15 text-teal ring-teal/30",
  unhealthy: "bg-amber-400/15 text-amber-600 ring-amber-400/30",
  unreachable: "bg-red-500/10 text-red-600 ring-red-500/30",
  provisioning: "bg-primary/10 text-primary ring-primary/30",
  stopped: "bg-muted text-muted-foreground ring-border",
  failed: "bg-red-500/10 text-red-600 ring-red-500/30",
};

export function Pill({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", tone)}>
      {children}
    </span>
  );
}

export function HealthPill({ state }: { state: DeploymentHealthState }) {
  const label = state.charAt(0).toUpperCase() + state.slice(1);
  return (
    <Pill tone={HEALTH_STYLE[state] ?? HEALTH_STYLE.stopped}>
      {state === "live" ? <span className="size-1.5 rounded-full bg-teal animate-pulse" aria-hidden /> : null}
      {label}
    </Pill>
  );
}

export function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function normalizeModelName(name: string) {
  return name.trim().toLowerCase();
}

// Dynamic route segments can arrive still percent-encoded, so decode them before matching names.
export function decodeRouteParam(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

// Duplicate names (legacy data) carry the model id so the URL stays unambiguous.
export function modelHref(model: Pick<ModelSummary, "id" | "name">, duplicateName: boolean) {
  const base = `/models/${encodeURIComponent(model.name)}`;
  return duplicateName ? `${base}?id=${encodeURIComponent(model.id)}` : base;
}

export function versionHref(model: Pick<ModelSummary, "id" | "name">, version: number, duplicateName: boolean) {
  const base = `${modelHref(model, false)}/${version}`;
  return duplicateName ? `${base}?id=${encodeURIComponent(model.id)}` : base;
}
