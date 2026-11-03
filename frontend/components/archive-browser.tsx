"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Archive, Boxes, Download, RotateCcw, Server, X } from "lucide-react";
import { useMemo, useState } from "react";

import { formatWhen } from "@/components/models-ui";
import {
  useArchivedModels,
  useDeploymentArchive,
  useDownloadArchivedModel,
  useRestoreModel,
} from "@/lib/queries";
import { ApiError } from "@/lib/api";
import type { ArchivedDeployment, ArchivedModel, ArchivedVersion } from "@/lib/types";
import { cn } from "@/lib/utils";

type Folder = "models" | "containers";

const RETENTION_DAYS = 7;
const DAY_MS = 86_400_000;

function daysLeft(purgeAt: string | null | undefined) {
  if (!purgeAt) return RETENTION_DAYS;
  return Math.max(0, Math.min(RETENTION_DAYS, Math.ceil((Date.parse(purgeAt) - Date.now()) / DAY_MS)));
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError && error.detail?.code === "name_taken") {
    return `A model named "${String(error.detail.name)}" already exists. Rename or delete it, then restore again.`;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}

export function ArchiveBrowser({ modelNames }: { modelNames: Map<string, string> }) {
  const [open, setOpen] = useState(false);
  const [folder, setFolder] = useState<Folder>("models");
  const archivedModels = useArchivedModels();
  const archivedContainers = useDeploymentArchive();
  const models = useMemo(() => archivedModels.data ?? [], [archivedModels.data]);
  const containers = useMemo(() => archivedContainers.data ?? [], [archivedContainers.data]);

  const archivedNames = useMemo(() => new Map(models.map((model) => [model.id, model.name])), [models]);
  const names = useMemo(() => new Map([...archivedNames, ...modelNames]), [archivedNames, modelNames]);

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50">
        <Archive className="size-4 text-muted-foreground" aria-hidden />
        Archive
        <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs tabular-nums text-muted-foreground">
          {models.length + containers.length}
        </span>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex h-[min(80vh,40rem)] w-[min(96vw,56rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Archive</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                Deleted items stay here for {RETENTION_DAYS} days, then are permanently removed. Only you can see your archive.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
            <nav aria-label="Archive folders" className="flex shrink-0 gap-1 border-b border-border p-2 sm:w-52 sm:flex-col sm:border-b-0 sm:border-r">
              <FolderButton active={folder === "models"} onClick={() => setFolder("models")} icon={Boxes} label="Deleted models" count={models.length} />
              <FolderButton
                active={folder === "containers"}
                onClick={() => setFolder("containers")}
                icon={Server}
                label="Deallocated containers"
                count={containers.length}
              />
            </nav>
            <div className="min-h-0 flex-1 overflow-y-auto p-5">
              {folder === "models" ? (
                <ArchivedModelList models={models} isLoading={archivedModels.isLoading} error={archivedModels.error} />
              ) : (
                <ArchivedContainerList
                  containers={containers}
                  names={names}
                  isLoading={archivedContainers.isLoading}
                  error={archivedContainers.error}
                />
              )}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function FolderButton({
  active,
  onClick,
  icon: Icon,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Boxes;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "flex min-w-0 flex-1 items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors sm:flex-none",
        active ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="tabular-nums text-xs">{count}</span>
    </button>
  );
}

function ArchivedModelList({ models, isLoading, error }: { models: ArchivedModel[]; isLoading: boolean; error: Error | null }) {
  const [restoreError, setRestoreError] = useState<{ id: string; message: string } | null>(null);
  const restore = useRestoreModel();
  const download = useDownloadArchivedModel();

  if (error) return <p className="text-sm text-destructive">{error.message}</p>;
  if (isLoading) return <div className="h-16 animate-pulse rounded-lg bg-muted" aria-hidden />;
  if (models.length === 0) return <p className="text-sm text-muted-foreground">No deleted models.</p>;

  return (
    <ul className="divide-y divide-border">
      {models.map((model) => {
        const days = daysLeft(model.purge_at);
        const busy = restore.isPending && restore.variables === model.id;
        const downloading = download.isPending && download.variables?.modelId === model.id;
        return (
          <li key={model.id} className="flex flex-col gap-3 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{model.name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {model.version_count} version{model.version_count === 1 ? "" : "s"} · deleted {formatWhen(model.archived_at)}
                </p>
              </div>
              <Days days={days} />
            </div>

            <ul className="flex flex-col gap-1.5 rounded-lg bg-muted/40 p-2">
              {model.versions.map((version) => (
                <VersionRow key={version.version} version={version} />
              ))}
            </ul>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={downloading}
                onClick={() => {
                  setRestoreError(null);
                  download.mutate({ modelId: model.id, fallbackName: `${model.name}.zip` });
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-card px-3 text-xs font-medium hover:bg-muted disabled:opacity-60"
              >
                <Download className="size-3.5" aria-hidden />
                {downloading ? "Preparing…" : "Download"}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setRestoreError(null);
                  restore.mutate(model.id, {
                    onError: (err) => setRestoreError({ id: model.id, message: errorMessage(err) }),
                  });
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-white hover:bg-primary/90 disabled:opacity-60"
              >
                <RotateCcw className="size-3.5" aria-hidden />
                {busy ? "Restoring…" : "Restore"}
              </button>
            </div>

            {download.isError && download.variables?.modelId === model.id ? (
              <p className="text-xs text-destructive">{errorMessage(download.error)}</p>
            ) : null}
            {restoreError?.id === model.id ? <p className="text-xs text-destructive">{restoreError.message}</p> : null}
          </li>
        );
      })}
    </ul>
  );
}

function VersionRow({ version }: { version: ArchivedVersion }) {
  return (
    <li className="flex flex-wrap items-center gap-2 text-xs">
      <span className="rounded-md bg-card px-2 py-0.5 font-mono font-medium">v{version.version}</span>
      <span className="rounded-md bg-card px-2 py-0.5 font-mono text-muted-foreground ring-1 ring-inset ring-border" title="Training job ID">
        job {version.job_id.slice(0, 8)}
      </span>
      {version.kpi ? <span className="text-muted-foreground">KPI {version.kpi}</span> : null}
      <span className="text-muted-foreground">{formatWhen(version.created_at)}</span>
    </li>
  );
}

function ArchivedContainerList({
  containers,
  names,
  isLoading,
  error,
}: {
  containers: ArchivedDeployment[];
  names: Map<string, string>;
  isLoading: boolean;
  error: Error | null;
}) {
  if (error) return <p className="text-sm text-destructive">{error.message}</p>;
  if (isLoading) return <div className="h-16 animate-pulse rounded-lg bg-muted" aria-hidden />;
  if (containers.length === 0) return <p className="text-sm text-muted-foreground">No deallocated containers.</p>;

  return (
    <ul className="divide-y divide-border">
      {containers.map((item) => (
        <ContainerRow
          key={item.id}
          item={item}
          modelName={names.get(item.model_id) ?? `Model ${item.model_id.slice(0, 8)}`}
        />
      ))}
    </ul>
  );
}

function ContainerRow({ item, modelName }: { item: ArchivedDeployment; modelName: string }) {
  const days = Math.max(0, Math.min(RETENTION_DAYS, item.days_remaining));
  return (
    <li className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">
          {modelName} <span className="font-mono text-xs text-muted-foreground">v{item.version}</span>
        </p>
        <p className="mt-0.5 font-mono text-xs text-muted-foreground">{item.container}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Stopped {formatWhen(item.archived_at)}
          {item.created_by_email ? ` · ${item.created_by_email}` : ""}
        </p>
      </div>
      <Days days={days} />
    </li>
  );
}

function Days({ days }: { days: number }) {
  const urgent = days <= 1;
  return (
    <div className="flex w-full items-center gap-3 sm:w-56">
      <div
        role="meter"
        aria-label="Days until permanent deletion"
        aria-valuemin={0}
        aria-valuemax={RETENTION_DAYS}
        aria-valuenow={days}
        aria-valuetext={`${days} of ${RETENTION_DAYS} days remaining`}
        className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-all duration-500", urgent ? "bg-destructive" : "bg-primary")}
          style={{ width: `${(days / RETENTION_DAYS) * 100}%` }}
        />
      </div>
      <span className={cn("shrink-0 whitespace-nowrap text-xs tabular-nums", urgent ? "text-destructive" : "text-muted-foreground")}>
        {days} of {RETENTION_DAYS} days left
      </span>
    </div>
  );
}
