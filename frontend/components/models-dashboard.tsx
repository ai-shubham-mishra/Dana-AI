"use client";

import { Boxes, Loader2, Play, RefreshCw, Square, Terminal } from "lucide-react";
import { useMemo, useState } from "react";

import { CollapsibleSection } from "@/components/collapsible-section";
import { KeyValueTree } from "@/components/key-value-tree";
import { LogTerminal } from "@/components/log-terminal";
import { RetrainDialog } from "@/components/retrain-dialog";
import { useDeploymentLogs } from "@/lib/deployment-logs";
import {
  useAllocateDeployment,
  useDeallocateDeployment,
  useDeployments,
  useModel,
  useModels,
  useRetrainVersion,
} from "@/lib/queries";
import type { Deployment, DeploymentHealthState, ModelVersion } from "@/lib/types";
import { cn } from "@/lib/utils";

const HEALTH_STYLE: Record<string, string> = {
  live: "bg-teal/15 text-teal ring-teal/30",
  unhealthy: "bg-amber-400/15 text-amber-600 ring-amber-400/30",
  unreachable: "bg-red-500/10 text-red-600 ring-red-500/30",
  provisioning: "bg-primary/10 text-primary ring-primary/30",
  stopped: "bg-muted text-muted-foreground ring-border",
  failed: "bg-red-500/10 text-red-600 ring-red-500/30",
};

function Pill({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", tone)}>
      {children}
    </span>
  );
}

function HealthPill({ state }: { state: DeploymentHealthState }) {
  const label = state.charAt(0).toUpperCase() + state.slice(1);
  return (
    <Pill tone={HEALTH_STYLE[state] ?? HEALTH_STYLE.stopped}>
      {state === "live" ? <span className="size-1.5 rounded-full bg-teal animate-pulse" aria-hidden /> : null}
      {label}
    </Pill>
  );
}

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function ModelList({
  selectedId,
  onSelect,
  deployments,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
  deployments: Deployment[];
}) {
  const models = useModels();
  const liveByModel = useMemo(() => {
    const counts = new Map<string, number>();
    for (const dep of deployments) {
      if (dep.health.state === "live") counts.set(dep.model_id, (counts.get(dep.model_id) ?? 0) + 1);
    }
    return counts;
  }, [deployments]);

  return (
    <aside className="space-y-2">
      <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Models</h2>
      {models.isLoading ? <p className="px-1 text-sm text-muted-foreground">Loading…</p> : null}
      {models.data?.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
          No models yet. Finish a training job to create one.
        </p>
      ) : null}
      <ul className="space-y-1.5">
        {models.data?.map((model) => {
          const active = model.id === selectedId;
          const live = liveByModel.get(model.id) ?? 0;
          return (
            <li key={model.id}>
              <button
                type="button"
                onClick={() => onSelect(model.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "group w-full rounded-lg border px-3 py-2.5 text-left transition-all duration-200",
                  active
                    ? "border-primary/40 bg-primary/5 shadow-elevated"
                    : "border-transparent hover:border-border hover:bg-muted/50",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium">{model.name}</span>
                  {live > 0 ? <Pill tone={HEALTH_STYLE.live}>{live} live</Pill> : null}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  v{model.latest_version} · {model.version_count} version{model.version_count === 1 ? "" : "s"}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function DeploymentCard({
  deployment,
  selected,
  onSelectLogs,
}: {
  deployment: Deployment;
  selected: boolean;
  onSelectLogs: () => void;
}) {
  const deallocate = useDeallocateDeployment();
  const [confirming, setConfirming] = useState(false);
  const busy = deployment.status === "provisioning" || deallocate.isPending;
  const canStop = deployment.status === "running" || deployment.status === "provisioning";

  return (
    <div
      className={cn(
        "rounded-xl border bg-card p-4 transition-all duration-200",
        selected ? "border-primary/50 shadow-elevated" : "border-border",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold">v{deployment.version}</span>
            <Pill tone={HEALTH_STYLE[deployment.status] ?? HEALTH_STYLE.stopped}>{deployment.status}</Pill>
            <HealthPill state={deployment.health.state} />
          </div>
          <a
            href={deployment.url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-block font-mono text-xs text-primary hover:underline"
          >
            {deployment.url}
          </a>
          <div className="mt-0.5 text-xs text-muted-foreground">
            Port {deployment.host_port} · {deployment.created_by_email ?? "unknown"} · {formatWhen(deployment.created_at)}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSelectLogs}
            aria-pressed={selected}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              selected ? "border-primary bg-primary text-white" : "border-border hover:bg-muted",
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
    </div>
  );
}

function VersionRow({
  version,
  selected,
  onSelect,
  onRetrain,
  onAllocate,
  allocating,
}: {
  version: ModelVersion;
  selected: boolean;
  onSelect: () => void;
  onRetrain: () => void;
  onAllocate: () => void;
  allocating: boolean;
}) {
  return (
    <li
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors",
        selected ? "border-primary/40 bg-primary/5" : "border-border hover:bg-muted/40",
      )}
    >
      <button type="button" onClick={onSelect} className="min-w-0 text-left">
        <div className="text-sm font-semibold">Version {version.version}</div>
        <div className="text-xs text-muted-foreground">
          {version.source}
          {version.source_version ? ` from v${version.source_version}` : ""}
          {version.kpi ? ` · KPI ${version.kpi}` : ""} · {version.created_by_email ?? "unknown"} · {formatWhen(version.created_at)}
        </div>
      </button>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRetrain}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-muted"
        >
          <RefreshCw className="size-3.5" aria-hidden />
          Retrain
        </button>
        <button
          type="button"
          onClick={onAllocate}
          disabled={allocating}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {allocating ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
          Allocate container
        </button>
      </div>
    </li>
  );
}

function ModelWorkspace({ modelId, deployments }: { modelId: string; deployments: Deployment[] }) {
  const model = useModel(modelId);
  const allocate = useAllocateDeployment();
  const retrain = useRetrainVersion();
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [retrainTarget, setRetrainTarget] = useState<ModelVersion | null>(null);
  const [selectedDeploymentId, setSelectedDeploymentId] = useState<string | null>(null);
  const [retrainJobId, setRetrainJobId] = useState<string | null>(null);

  const versions = model.data?.versions ?? [];
  const current = versions.find((v) => v.version === selectedVersion) ?? versions[0] ?? null;
  const modelDeployments = deployments.filter((d) => d.model_id === modelId);
  const selectedDeployment = modelDeployments.find((d) => d.id === selectedDeploymentId) ?? null;
  const logs = useDeploymentLogs(selectedDeployment?.id ?? null);

  async function confirmRetrain() {
    if (!retrainTarget) return;
    const result = await retrain.mutateAsync({ modelId, version: retrainTarget.version });
    setRetrainJobId(result.job_id);
    setRetrainTarget(null);
  }

  return (
    <div className="min-w-0 space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{model.data?.name ?? "Model"}</h1>
          <p className="text-sm text-muted-foreground">
            {versions.length} version{versions.length === 1 ? "" : "s"} · retrain from any version or serve it in a local container
          </p>
        </div>
        {retrainJobId ? (
          <Pill tone={HEALTH_STYLE.live}>Retraining queued · job {retrainJobId.slice(0, 8)}</Pill>
        ) : null}
      </header>

      {allocate.error ? <p className="text-sm text-destructive">{allocate.error.message}</p> : null}

      <CollapsibleSection title="Versions" count={versions.length}>
        <ul className="space-y-2">
          {versions.map((version) => (
            <VersionRow
              key={version.version}
              version={version}
              selected={current?.version === version.version}
              onSelect={() => setSelectedVersion(version.version)}
              onRetrain={() => setRetrainTarget(version)}
              onAllocate={() => allocate.mutate({ modelId, version: version.version })}
              allocating={allocate.isPending && allocate.variables?.version === version.version}
            />
          ))}
        </ul>
      </CollapsibleSection>

      {current ? (
        <CollapsibleSection title={`Configuration · v${current.version}`} defaultOpen={false}>
          <div className="rounded-xl border border-border bg-card p-4">
            <KeyValueTree data={current.params ?? {}} />
          </div>
        </CollapsibleSection>
      ) : null}

      <CollapsibleSection title="Containers" count={modelDeployments.length}>
        {modelDeployments.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            No containers for this model. Allocate one from a version above.
          </p>
        ) : (
          <div className="space-y-3">
            {modelDeployments.map((deployment) => (
              <DeploymentCard
                key={deployment.id}
                deployment={deployment}
                selected={deployment.id === selectedDeploymentId}
                onSelectLogs={() => setSelectedDeploymentId(deployment.id === selectedDeploymentId ? null : deployment.id)}
              />
            ))}
          </div>
        )}
      </CollapsibleSection>

      {selectedDeployment ? (
        <CollapsibleSection title={`Live logs · v${selectedDeployment.version}`}>
          <LogTerminal
            title={selectedDeployment.container}
            lines={logs.lines}
            state={logs.state}
            error={logs.error}
          />
        </CollapsibleSection>
      ) : null}

      {model.data && model.data.events.length > 0 ? (
        <CollapsibleSection title="History" count={model.data.events.length} defaultOpen={false}>
          <ol className="space-y-2 border-l border-border pl-4">
            {model.data.events.map((event, index) => (
              <li key={index} className="text-sm">
                <span className="font-medium">{event.action.replaceAll("_", " ")}</span>
                {event.version ? <span className="text-muted-foreground"> · v{event.version}</span> : null}
                <div className="text-xs text-muted-foreground">
                  {event.actor_email ?? "system"} · {formatWhen(event.created_at)}
                  {event.detail ? ` · ${event.detail}` : ""}
                </div>
              </li>
            ))}
          </ol>
        </CollapsibleSection>
      ) : null}

      {retrainTarget ? (
        <RetrainDialog
          modelName={model.data?.name ?? "model"}
          version={retrainTarget}
          pending={retrain.isPending}
          error={retrain.error?.message ?? null}
          onConfirm={confirmRetrain}
          onOpenChange={(open) => {
            if (!open) setRetrainTarget(null);
          }}
        />
      ) : null}
    </div>
  );
}

export function ModelsDashboard() {
  const deployments = useDeployments();
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const models = useModels();
  const activeModelId = selectedModelId ?? models.data?.[0]?.id ?? null;

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <ModelList selectedId={activeModelId} onSelect={setSelectedModelId} deployments={deployments.data ?? []} />
      {activeModelId ? (
        <ModelWorkspace key={activeModelId} modelId={activeModelId} deployments={deployments.data ?? []} />
      ) : (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-12 text-center">
          <Boxes className="mb-3 size-8 text-muted-foreground" aria-hidden />
          <p className="text-sm text-muted-foreground">Select a model to see its versions and containers.</p>
        </div>
      )}
    </div>
  );
}
