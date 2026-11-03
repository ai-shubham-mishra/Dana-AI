"use client";

import { Loader2, Square, Terminal } from "lucide-react";
import { useState } from "react";

import { LogTerminal } from "@/components/log-terminal";
import { HEALTH_STYLE, HealthPill, Pill, formatWhen } from "@/components/models-ui";
import { useDeploymentLogs } from "@/lib/deployment-logs";
import { useDeallocateDeployment } from "@/lib/queries";
import type { Deployment } from "@/lib/types";
import { cn } from "@/lib/utils";

export function DeploymentCard({ deployment }: { deployment: Deployment }) {
  const deallocate = useDeallocateDeployment();
  const [confirming, setConfirming] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);
  const logs = useDeploymentLogs(logsOpen ? deployment.id : null);
  const busy = deployment.status === "provisioning" || deallocate.isPending;
  const canStop = deployment.status === "running" || deployment.status === "provisioning";

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4 transition-all duration-200",
        logsOpen ? "border-primary/50 shadow-elevated" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">v{deployment.version}</span>
            <Pill tone={HEALTH_STYLE[deployment.status] ?? HEALTH_STYLE.stopped}>{deployment.status}</Pill>
            <HealthPill state={deployment.health.state} />
            {deployment.status === "provisioning" && deployment.stage ? (
              <span className="text-xs text-muted-foreground">{deployment.stage}</span>
            ) : null}
          </div>
          <a
            href={deployment.url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block break-all font-mono text-xs text-primary hover:underline"
          >
            {deployment.url}
          </a>
          <div className="mt-0.5 text-xs text-muted-foreground">
            Port {deployment.host_port} · {deployment.created_by_email ?? "not recorded"} · {formatWhen(deployment.created_at)}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setLogsOpen((open) => !open)}
            aria-pressed={logsOpen}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              logsOpen ? "border-primary bg-primary text-white" : "border-border hover:bg-muted",
            )}
          >
            <Terminal className="size-3.5" aria-hidden />
            Logs
          </button>
          {canStop && !confirming ? (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
            >
              <Square className="size-3.5" aria-hidden />
              Deallocate
            </button>
          ) : null}
          {confirming ? (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => {
                  deallocate.mutate(deployment.id, { onSettled: () => setConfirming(false) });
                }}
                disabled={deallocate.isPending}
                className="inline-flex items-center gap-1.5 rounded-md bg-destructive px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                {deallocate.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
                Stop container
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded-md px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-muted"
              >
                Keep
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {deployment.health.detail && deployment.health.state !== "live" ? (
        <p className="mt-3 text-xs text-muted-foreground">{deployment.health.detail}</p>
      ) : null}
      {deployment.error ? <p className="mt-3 text-xs text-destructive">{deployment.error}</p> : null}
      {deallocate.error ? <p className="mt-3 text-xs text-destructive">{deallocate.error.message}</p> : null}

      {logsOpen ? (
        <div className="mt-4">
          <LogTerminal
            title={`${deployment.container} · v${deployment.version}`}
            lines={logs.lines}
            state={logs.state}
            error={logs.error}
          />
        </div>
      ) : null}
    </div>
  );
}
