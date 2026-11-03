"use client";

import { ChevronRight, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { CollapsibleSection } from "@/components/collapsible-section";
import { DeleteModelDialog } from "@/components/delete-model-dialog";
import { ModelResolver, Shell } from "@/components/model-shell";
import { HEALTH_STYLE, Pill, formatWhen, versionHref } from "@/components/models-ui";
import { useDeleteModel, useDeployments, useModel } from "@/lib/queries";
import type { Deployment, ModelVersion } from "@/lib/types";

const ACTIVE_STATUSES = new Set(["provisioning", "running"]);

function isActive(deployment: Deployment) {
  return ACTIVE_STATUSES.has(deployment.status);
}

export function ModelDetailView({ name, modelId }: { name: string; modelId: string | null }) {
  return (
    <ModelResolver name={name} modelId={modelId}>
      {(resolvedId, duplicate) => <ModelWorkspace key={resolvedId} modelId={resolvedId} duplicate={duplicate} />}
    </ModelResolver>
  );
}

function VersionLink({ href, version, running }: { href: string; version: ModelVersion; running: boolean }) {
  const tags = version.tags ?? [];
  return (
    <li>
      <Link
        href={href}
        className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3 transition-colors hover:border-primary/40 hover:bg-muted/40"
      >
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">Version {version.version}</span>
            {version.job_id ? (
              <span title={version.job_id} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                job {version.job_id.slice(0, 8)}
              </span>
            ) : null}
            {tags.map((tag) => (
              <span
                key={tag}
                className={tag === "latest" ? "rounded-full bg-primary/15 px-2 py-0.5 text-[11px] font-medium text-primary" : "rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground"}
              >
                {tag}
              </span>
            ))}
            {running ? <Pill tone={HEALTH_STYLE.live}>container running</Pill> : null}
          </div>
          <div className="truncate text-xs text-muted-foreground">
            {version.source}
            {version.source_version ? ` from v${version.source_version}` : ""}
            {version.kpi ? ` · KPI ${version.kpi}` : ""} · {version.created_by_email ?? "unknown"} · {formatWhen(version.created_at)}
          </div>
        </div>
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      </Link>
    </li>
  );
}

function ModelWorkspace({ modelId, duplicate }: { modelId: string; duplicate: boolean }) {
  const router = useRouter();
  const model = useModel(modelId);
  const deployments = useDeployments();
  const deleteModel = useDeleteModel();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const data = model.data;
  const versions = data?.versions ?? [];
  const activeDeployments = (deployments.data ?? []).filter((d) => d.model_id === modelId && isActive(d));

  if (model.error?.status === 404) {
    return (
      <Shell crumbs={[{ label: "All models", href: "/models" }]}>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          This model no longer exists. It may have been deleted.
        </p>
      </Shell>
    );
  }

  if (!data) {
    return (
      <Shell crumbs={[{ label: "All models", href: "/models" }]}>
        <p className="text-sm text-muted-foreground">{model.error ? model.error.message : "Loading…"}</p>
      </Shell>
    );
  }

  async function confirmDelete(deallocate: boolean) {
    setDeleteError(null);
    try {
      await deleteModel.mutateAsync({ modelId, deallocate });
      router.push("/models");
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Delete failed");
    }
  }

  return (
    <Shell crumbs={[{ label: "All models", href: "/models" }, { label: data.name }]}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{data.name}</h1>
          <p className="text-sm text-muted-foreground">
            {versions.length} version{versions.length === 1 ? "" : "s"} · open a version to retrain it, allocate a container, or browse its artifacts
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setDeleteError(null);
            setDeleteOpen(true);
          }}
          className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-1.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
        >
          <Trash2 className="size-3.5" aria-hidden />
          Delete model
        </button>
      </header>

      <CollapsibleSection title="Versions" count={versions.length}>
        <ul className="space-y-2">
          {versions.map((version) => (
            <VersionLink
              key={version.version}
              href={versionHref({ id: modelId, name: data.name }, version.version, duplicate)}
              version={version}
              running={activeDeployments.some((d) => d.version === version.version)}
            />
          ))}
        </ul>
      </CollapsibleSection>

      {data.events.length > 0 ? (
        <CollapsibleSection title="History" count={data.events.length} defaultOpen={false}>
          <ol className="space-y-2 border-l border-border pl-4">
            {data.events.map((event, index) => (
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

      {deleteOpen ? (
        <DeleteModelDialog
          title={`Delete ${data.name}?`}
          description="This removes every version of the model and deletes its training jobs and artifacts."
          confirmLabel="Delete model"
          containers={activeDeployments}
          pending={deleteModel.isPending}
          error={deleteError}
          onConfirm={confirmDelete}
          onOpenChange={(open) => {
            if (!open && !deleteModel.isPending) setDeleteOpen(false);
          }}
        />
      ) : null}
    </Shell>
  );
}
