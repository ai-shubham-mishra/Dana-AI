"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Download, FileText, Loader2, X } from "lucide-react";
import { useState } from "react";

import { useDownloadVersionArtifact, useVersionArtifacts } from "@/lib/queries";
import type { VersionArtifact } from "@/lib/types";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong";
}

function ArtifactRow({
  artifact,
  downloading,
  onDownload,
}: {
  artifact: VersionArtifact;
  downloading: boolean;
  onDownload: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0">
          <div className="truncate font-mono text-sm">{artifact.name}</div>
          <div className="text-xs tabular-nums text-muted-foreground">{formatBytes(artifact.bytes)}</div>
        </div>
      </div>
      {artifact.stored ? (
        <button
          type="button"
          onClick={onDownload}
          disabled={downloading}
          aria-label={`Download ${artifact.name}`}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
        >
          {downloading ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Download className="size-3.5" aria-hidden />}
          Download
        </button>
      ) : (
        <span className="shrink-0 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground" title="This file was not kept after training">
          Not stored
        </span>
      )}
    </li>
  );
}

export function VersionArtifactsDialog({
  modelId,
  version,
  onOpenChange,
}: {
  modelId: string;
  version: number;
  onOpenChange: (open: boolean) => void;
}) {
  const artifacts = useVersionArtifacts(modelId, version);
  const download = useDownloadVersionArtifact();
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const items = artifacts.data ?? [];

  async function handleDownload(name: string) {
    setDownloadError(null);
    setDownloading(name);
    try {
      await download.mutateAsync({ modelId, version, name });
    } catch (error) {
      setDownloadError(errorMessage(error));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex h-[min(70vh,34rem)] w-[min(96vw,40rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Version {version} artifacts</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs text-muted-foreground">
                Files produced by this version&apos;s training run.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" aria-hidden />
            </Dialog.Close>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {artifacts.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading artifacts…
              </div>
            ) : artifacts.error ? (
              <p className="text-sm text-destructive">{errorMessage(artifacts.error)}</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No artifacts yet. Files appear here once the training run for this version finishes.
              </p>
            ) : (
              <ul className="space-y-2">
                {items.map((artifact) => (
                  <ArtifactRow
                    key={artifact.name}
                    artifact={artifact}
                    downloading={downloading === artifact.name}
                    onDownload={() => handleDownload(artifact.name)}
                  />
                ))}
              </ul>
            )}
            {downloadError ? <p className="mt-3 text-sm text-destructive">{downloadError}</p> : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
