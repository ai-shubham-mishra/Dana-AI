"use client";

import { Loader2, Play, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CollapsibleSection } from "@/components/collapsible-section";
import { DeleteModelDialog } from "@/components/delete-model-dialog";
import { DeploymentCard } from "@/components/deployment-card";
import { JobProgressBar, JobTimeline, StatusBadge } from "@/components/job-primitives";
import { KeyValueTree } from "@/components/key-value-tree";
import { ModelResolver, Shell } from "@/components/model-shell";
import { Pill, formatWhen, modelHref, versionHref } from "@/components/models-ui";
import { RetrainDialog } from "@/components/retrain-dialog";
import { VersionArtifactsPanel } from "@/components/version-artifacts-panel";
import { useAllocateDeployment, useDeleteVersion, useDeployments, useJob, useModel, useRetrainVersion } from "@/lib/queries";
import type { Deployment } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["provisioning", "running"]);

export function ModelVersionView({ name, modelId, version }: { name: string; modelId: string | null; version: number }) {
  return (
    <ModelResolver name={name} modelId={modelId}>
      {(resolvedId, duplicate) => (
        <VersionWorkspace key={resolvedId} modelId={resolvedId} duplicate={duplicate} routeName={name} version={version} />
      )}
    </ModelResolver>
  );
}

function TrainingJobSection({ jobId }: { jobId: string }) {
  const job = useJob(jobId);
  return (
    <CollapsibleSection title="Training job" count={job.data?.events.length}>
      {job.error ? (
        <p className="text-sm text-destructive">{job.error.message}</p>
      ) : job.data ? (
        <div className="space-y-4 rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="min-w-0 truncate text-sm font-medium">{job.data.title}</span>
            <StatusBadge status={job.data.status} />
          </div>
          <JobProgressBar percent={job.data.percent} status={job.data.status} />
          <JobTimeline events={job.data.events} status={job.data.status} percent={job.data.percent} />
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Loading training job…</p>
      )}
    </CollapsibleSection>
  );
}

function VersionWorkspace({
  modelId,
  duplicate,
  routeName,
  version,
}: {
  modelId: string;
  duplicate: boolean;
  routeName: string;
  version: number;
}) {
  const router = useRouter();
  const model = useModel(modelId);
  const deployments = useDeployments();
  const allocate = useAllocateDeployment();
  const retrain = useRetrainVersion();
  const deleteVersion = useDeleteVersion();
  const [retrainOpen, setRetrainOpen] = useState(false);
  const [retrainJobId, setRetrainJobId] = useState<string | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const retrainJob = useJob(retrainJobId);
  const retrainStatus = retrainJob.data?.status;
  const retrainActive = retrainStatus === "queued" || retrainStatus === "running";
  const retrainFinished = retrainStatus === "succeeded" || retrainStatus === "failed";
  const { refetch: refetchModel } = model;
  useEffect(() => {
    if (retrainFinished) void refetchModel();
  }, [retrainFinished, refetchModel]);

  const data = model.data;
  const versions = data?.versions ?? [];
  const record = versions.find((item) => item.version === version) ?? null;
  const versionDeployments = (deployments.data ?? []).filter((d) => d.model_id === modelId && d.version === version);
  const activeDeployments = versionDeployments.filter((d) => ACTIVE_STATUSES.has(d.status));
  const activeDeployment: Deployment | null = activeDeployments[0] ?? null;
  const provisioning = activeDeployment?.status === "provisioning";
  const allocating = allocate.isPending && allocate.variables?.version === version;
  const busy = allocating || activeDeployment !== null;
  const notFound = model.error?.status === 404;
  const modelName = data?.name ?? routeName;
  const modelPath = modelHref({ id: modelId, name: modelName }, duplicate);
  const crumbs = [
    { label: "All models", href: "/models" },
    { label: modelName, href: modelPath },
    { label: `Version ${version}` },
  ];

  async function confirmRetrain() {
    try {
      const result = await retrain.mutateAsync({ modelId, version });
      setRetrainJobId(result.job_id);
      setRetrainOpen(false);
    } catch {
      // The dialog shows retrain.error.
    }
  }

  async function confirmDelete(deallocate: boolean) {
    setDeleteError(null);
    try {
      await deleteVersion.mutateAsync({ modelId, version, deallocate });
      setDeleteOpen(false);
      router.push(versions.length > 1 ? modelPath : "/models");
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Delete failed");
    }
  }

  if (notFound) {
    return (
      <Shell crumbs={[{ label: "All models", href: "/models" }]}>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          This model no longer exists. It may have been deleted.
        </p>
      </Shell>
    );
  }

  if (model.isLoading || (!data && !model.error)) {
    return (
      <Shell crumbs={crumbs}>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </Shell>
    );
  }

  if (!record || !data) {
    return (
      <Shell crumbs={crumbs}>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Version {version} was not found on this model.
        </p>
      </Shell>
    );
  }

  const history = data.events.filter((event) => event.version === version);
  const configuration = record.params ?? {};
  const metrics = record.metrics ?? {};

  return (
    <Shell crumbs={crumbs}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Version {version}</h1>
            {record.tags.map((tag) => (
              <span
                key={tag}
                className={
                  tag === "latest"
                    ? "rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary"
                    : "rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                }
              >
                {tag}
              </span>
            ))}
            {record.job_id ? (
              <span title={record.job_id} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                job {record.job_id.slice(0, 8)}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {data.name} · {record.source}
            {record.source_version ? ` from v${record.source_version}` : ""}
            {record.kpi ? ` · KPI ${record.kpi}` : ""} · {record.created_by_email ?? "unknown"} · {formatWhen(record.created_at)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setRetrainOpen(true)}
            disabled={retrainActive}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="size-3.5" aria-hidden />
            Retrain
          </button>
          <button
            type="button"
            onClick={() => allocate.mutate({ modelId, version })}
            disabled={busy}
            aria-busy={busy}
            title={activeDeployment && !provisioning ? "This version already has a running container. Deallocate it to allocate again." : undefined}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {allocating || provisioning ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Play className="size-3.5" aria-hidden />}
            {allocating || provisioning ? "Allocating…" : activeDeployment ? "Container running" : "Allocate container"}
          </button>
          <button
            type="button"
            onClick={() => {
              setDeleteError(null);
              setDeleteOpen(true);
            }}
            className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
          >
            <Trash2 className="size-3.5" aria-hidden />
            Delete version
          </button>
        </div>
      </header>

      {allocate.error ? <p className="text-sm text-destructive">{allocate.error.message}</p> : null}

      {allocating || provisioning ? (
        <div className="space-y-1.5 rounded-xl border border-primary/30 bg-card p-4">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="truncate text-muted-foreground">{activeDeployment?.stage ?? "Starting allocation"}</span>
            <span className="font-mono tabular-nums text-primary">{Math.round(activeDeployment?.percent ?? 0)}%</span>
          </div>
          <JobProgressBar percent={activeDeployment?.percent ?? 0} status="running" />
        </div>
      ) : null}

      {retrainJobId && retrainJob.data ? (
        <div className="space-y-1.5 rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
            <span className="truncate text-muted-foreground">
              Retrain job {retrainJobId.slice(0, 8)} · {retrainJob.data.message ?? retrainJob.data.stage ?? retrainJob.data.status}
            </span>
            <span className="flex items-center gap-2">
              <Pill tone={retrainStatus === "failed" ? "bg-red-500/10 text-red-600 ring-red-500/30" : "bg-primary/10 text-primary ring-primary/30"}>
                {retrainJob.data.status}
              </Pill>
              {retrainStatus === "succeeded" && data.latest_version !== version ? (
                <Link href={versionHref({ id: modelId, name: modelName }, data.latest_version, duplicate)} className="text-primary hover:underline">
                  Open v{data.latest_version}
                </Link>
              ) : null}
            </span>
          </div>
          {retrainActive ? <JobProgressBar percent={retrainJob.data.percent} status={retrainJob.data.status} /> : null}
        </div>
      ) : null}

      <CollapsibleSection title="Containers" count={versionDeployments.length}>
        {versionDeployments.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            No containers for this version. Allocate one above.
          </p>
        ) : (
          <div className="space-y-3">
            {versionDeployments.map((deployment) => (
              <DeploymentCard key={deployment.id} deployment={deployment} />
            ))}
          </div>
        )}
      </CollapsibleSection>

      <CollapsibleSection title="Artifacts">
        <VersionArtifactsPanel modelId={modelId} version={version} />
      </CollapsibleSection>

      {record.job_id ? <TrainingJobSection jobId={record.job_id} /> : null}

      <CollapsibleSection title="Configuration" defaultOpen={false}>
        <div className="rounded-xl border border-border bg-card p-4">
          <KeyValueTree data={configuration} />
        </div>
      </CollapsibleSection>

      {Object.keys(metrics).length > 0 ? (
        <CollapsibleSection title="Metrics" defaultOpen={false}>
          <div className="rounded-xl border border-border bg-card p-4">
            <KeyValueTree data={metrics} />
          </div>
        </CollapsibleSection>
      ) : null}

      <CollapsibleSection title="History" count={history.length} defaultOpen={false}>
        {history.length === 0 ? (
          <p className="text-sm text-muted-foreground">No history for this version yet.</p>
        ) : (
          <ol className="space-y-2 border-l border-border pl-4">
            {history.map((event, index) => (
              <li key={index} className="text-sm">
                <span className="font-medium">{event.action.replaceAll("_", " ")}</span>
                <div className="text-xs text-muted-foreground">
                  {event.actor_email ?? "system"} · {formatWhen(event.created_at)}
                  {event.detail ? ` · ${event.detail}` : ""}
                </div>
              </li>
            ))}
          </ol>
        )}
      </CollapsibleSection>

      {retrainOpen ? (
        <RetrainDialog
          modelName={modelName}
          version={record}
          pending={retrain.isPending}
          error={retrain.error?.message ?? null}
          onConfirm={confirmRetrain}
          onOpenChange={(open) => {
            if (!open) setRetrainOpen(false);
          }}
        />
      ) : null}

      {deleteOpen ? (
        <DeleteModelDialog
          title={`Delete version ${version}?`}
          description="This removes this version and its training job and artifacts."
          confirmLabel="Delete version"
          containers={activeDeployments}
          pending={deleteVersion.isPending}
          error={deleteError}
          onConfirm={confirmDelete}
          onOpenChange={(open) => {
            if (!open && !deleteVersion.isPending) setDeleteOpen(false);
          }}
        />
      ) : null}
    </Shell>
  );
}
