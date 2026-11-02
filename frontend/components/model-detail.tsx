"use client";

import { ChevronLeft, Loader2, Play, RefreshCw, Square, Tag, Terminal, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { CollapsibleSection } from "@/components/collapsible-section";
import { DeleteModelDialog } from "@/components/delete-model-dialog";
import { KeyValueTree } from "@/components/key-value-tree";
import { LogTerminal } from "@/components/log-terminal";
import { HEALTH_STYLE, HealthPill, Pill, formatWhen, modelHref, normalizeModelName } from "@/components/models-ui";
import { ProvisionProgress } from "@/components/provision-progress";
import { RetrainDialog } from "@/components/retrain-dialog";
import { useDeploymentLogs } from "@/lib/deployment-logs";
import {
  useAllocateDeployment,
  useDeallocateDeployment,
  useDeleteModel,
  useDeleteVersion,
  useDeployments,
  useModel,
  useModels,
  useRetrainVersion,
  useSetVersionTag,
} from "@/lib/queries";
import type { ApiError } from "@/lib/api";
import type { Deployment, ModelSummary, ModelVersion } from "@/lib/types";
import { cn } from "@/lib/utils";

const ACTIVE_STATUSES = new Set(["provisioning", "running"]);

function isActive(deployment: Deployment) {
  return ACTIVE_STATUSES.has(deployment.status);
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6 md:p-10">
      <Link href="/models" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" aria-hidden />
        All models
      </Link>
      {children}
    </div>
  );
}

function DuplicatePicker({ name, matches }: { name: string; matches: ModelSummary[] }) {
  const duplicate = matches.length > 1;
  return (
    <Shell>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{name}</h1>
        <p className="text-sm text-muted-foreground">Several models share this name. Choose which one to open.</p>
      </header>
      <ul className="grid gap-3 sm:grid-cols-2">
        {matches.map((model) => (
          <li key={model.id}>
            <Link
              href={modelHref(model, duplicate)}
              className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-all duration-200 hover:border-primary/40 hover:shadow-elevated"
            >
              <span className="text-sm font-semibold">
                v{model.latest_version} · {model.version_count} version{model.version_count === 1 ? "" : "s"}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{model.id}</span>
              <span className="text-xs text-muted-foreground">Created {formatWhen(model.created_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Shell>
  );
}

export function ModelDetailView({ name, modelId }: { name: string; modelId: string | null }) {
  const models = useModels();
  const matches = useMemo(
    () => (models.data ?? []).filter((model) => normalizeModelName(model.name) === normalizeModelName(name)),
    [models.data, name],
  );

  if (!modelId && models.isLoading) {
    return (
      <Shell>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </Shell>
    );
  }

  if (!modelId && matches.length > 1) return <DuplicatePicker name={name} matches={matches} />;

  const resolvedId = modelId ?? matches[0]?.id ?? null;
  if (!resolvedId) {
    return (
      <Shell>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No model named “{name}”. It may have been deleted.
        </p>
      </Shell>
    );
  }

  return <ModelWorkspace key={resolvedId} modelId={resolvedId} />;
}

function DeploymentCard({ deployment }: { deployment: Deployment }) {
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

function VersionRow({
  version,
  selected,
  onSelect,
  onRetrain,
  onAllocate,
  onDelete,
  onTag,
  allocating,
  tagging,
  provisioning,
}: {
  version: ModelVersion;
  selected: boolean;
  onSelect: () => void;
  onRetrain: () => void;
  onAllocate: () => void;
  onDelete: () => void;
  onTag: (tag: string) => void;
  allocating: boolean;
  tagging: boolean;
  provisioning: Deployment | null;
}) {
  const [draft, setDraft] = useState("");
  const tags = version.tags ?? [];
  const busy = allocating || provisioning !== null;
  return (
    <li
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors",
        selected ? "border-primary/40 bg-primary/5" : "border-border hover:bg-muted/40",
      )}
    >
      <button type="button" onClick={onSelect} className="min-w-0 text-left">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold">Version {version.version}</span>
          {tags.map((tag) => (
            <span
              key={tag}
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                tag === "latest" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
              )}
            >
              {tag}
            </span>
          ))}
        </div>
        <div className="text-xs text-muted-foreground">
          {version.source}
          {version.source_version ? ` from v${version.source_version}` : ""}
          {version.kpi ? ` · KPI ${version.kpi}` : ""} · {version.created_by_email ?? "unknown"} · {formatWhen(version.created_at)}
        </div>
      </button>
      <div className="flex flex-wrap items-center gap-2">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            const tag = draft.trim().toLowerCase();
            if (!tag) return;
            onTag(tag);
            setDraft("");
          }}
          className="flex items-center gap-1"
        >
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={32}
            placeholder="tag"
            aria-label={`Tag version ${version.version}`}
            className="w-24 rounded-md border border-border bg-background px-2 py-1.5 text-xs outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={!draft.trim() || tagging}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
          >
            {tagging ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Tag className="size-3.5" aria-hidden />}
            Tag
          </button>
        </form>
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
          disabled={busy}
          aria-busy={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-2.5 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
          {provisioning ? "Allocating…" : "Allocate container"}
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label={`Delete version ${version.version}`}
          className="inline-flex items-center rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="size-3.5" aria-hidden />
        </button>
      </div>
      {provisioning ? (
        <div className="basis-full">
          <ProvisionProgress percent={provisioning.percent} stage={provisioning.stage} />
        </div>
      ) : null}
    </li>
  );
}

type DeleteTarget = { kind: "model" } | { kind: "version"; version: ModelVersion };

function ModelWorkspace({ modelId }: { modelId: string }) {
  const router = useRouter();
  const model = useModel(modelId);
  const deployments = useDeployments();
  const allocate = useAllocateDeployment();
  const setTag = useSetVersionTag();
  const retrain = useRetrainVersion();
  const deleteModel = useDeleteModel();
  const deleteVersion = useDeleteVersion();
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [retrainTarget, setRetrainTarget] = useState<ModelVersion | null>(null);
  const [retrainJobId, setRetrainJobId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const versions = model.data?.versions ?? [];
  const current = versions.find((v) => v.version === selectedVersion) ?? versions[0] ?? null;
  const modelDeployments = (deployments.data ?? []).filter((d) => d.model_id === modelId);
  const activeDeployments = modelDeployments.filter(isActive);
  const notFound = (model.error as ApiError | null)?.status === 404;

  async function confirmRetrain() {
    if (!retrainTarget) return;
    const result = await retrain.mutateAsync({ modelId, version: retrainTarget.version });
    setRetrainJobId(result.job_id);
    setRetrainTarget(null);
  }

  async function confirmDelete(deallocate: boolean) {
    if (!deleteTarget) return;
    setDeleteError(null);
    try {
      if (deleteTarget.kind === "model") {
        await deleteModel.mutateAsync({ modelId, deallocate });
        router.push("/models");
        return;
      }
      const lastVersion = versions.length <= 1;
      await deleteVersion.mutateAsync({ modelId, version: deleteTarget.version.version, deallocate });
      setDeleteTarget(null);
      if (lastVersion) router.push("/models");
      else setSelectedVersion(null);
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Delete failed");
    }
  }

  if (notFound) {
    return (
      <Shell>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          This model no longer exists. It may have been deleted.
        </p>
      </Shell>
    );
  }

  const deleting = deleteModel.isPending || deleteVersion.isPending;
  const deleteContainers =
    deleteTarget?.kind === "version"
      ? activeDeployments.filter((d) => d.version === deleteTarget.version.version)
      : activeDeployments;

  return (
    <Shell>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{model.data?.name ?? "Model"}</h1>
          <p className="text-sm text-muted-foreground">
            {versions.length} version{versions.length === 1 ? "" : "s"} · retrain from any version or serve it in a local container
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {retrainJobId ? (
            <Pill tone={HEALTH_STYLE.live}>Retraining queued · job {retrainJobId.slice(0, 8)}</Pill>
          ) : null}
          {model.data ? (
            <button
              type="button"
              onClick={() => {
                setDeleteError(null);
                setDeleteTarget({ kind: "model" });
              }}
              className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
            >
              <Trash2 className="size-3.5" aria-hidden />
              Delete model
            </button>
          ) : null}
        </div>
      </header>

      {allocate.error ? <p className="text-sm text-destructive">{allocate.error.message}</p> : null}
      {setTag.error ? <p className="text-sm text-destructive">{setTag.error.message}</p> : null}

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
              onDelete={() => {
                setDeleteError(null);
                setDeleteTarget({ kind: "version", version });
              }}
              allocating={allocate.isPending && allocate.variables?.version === version.version}
              provisioning={
                activeDeployments.find((d) => d.version === version.version && d.status === "provisioning") ?? null
              }
              onTag={(tag) => setTag.mutate({ modelId, version: version.version, tag })}
              tagging={setTag.isPending && setTag.variables?.version === version.version}
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
              <DeploymentCard key={deployment.id} deployment={deployment} />
            ))}
          </div>
        )}
      </CollapsibleSection>

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

      {deleteTarget ? (
        <DeleteModelDialog
          title={deleteTarget.kind === "model" ? `Delete ${model.data?.name ?? "model"}?` : `Delete version ${deleteTarget.version.version}?`}
          description={
            deleteTarget.kind === "model"
              ? "This removes every version of the model and deletes its training jobs and artifacts."
              : "This removes this version and its training job and artifacts."
          }
          confirmLabel={deleteTarget.kind === "model" ? "Delete model" : "Delete version"}
          containers={deleteContainers}
          pending={deleting}
          error={deleteError}
          onConfirm={confirmDelete}
          onOpenChange={(open) => {
            if (!open && !deleting) setDeleteTarget(null);
          }}
        />
      ) : null}
    </Shell>
  );
}
