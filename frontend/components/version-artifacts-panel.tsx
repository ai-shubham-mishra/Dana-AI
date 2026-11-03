"use client";

import { Download, Eye, FileText, Loader2 } from "lucide-react";
import { useState } from "react";

import { ArtifactPreviewDialog } from "@/components/artifact-preview-dialog";
import { formatBytes, isPreviewableArtifact } from "@/lib/artifact-preview";
import { useDownloadVersionArtifact, useVersionArtifacts } from "@/lib/queries";
import type { VersionArtifact } from "@/lib/types";

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong";
}

function ArtifactRow({
  artifact,
  downloading,
  onView,
  onDownload,
}: {
  artifact: VersionArtifact;
  downloading: boolean;
  onView: () => void;
  onDownload: () => void;
}) {
  const previewable = artifact.stored && isPreviewableArtifact(artifact.name, artifact.bytes);
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
        <div className="flex shrink-0 items-center gap-2">
          {previewable ? (
            <button
              type="button"
              onClick={onView}
              aria-label={`View ${artifact.name}`}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
            >
              <Eye className="size-3.5" aria-hidden />
              View
            </button>
          ) : null}
          <button
            type="button"
            onClick={onDownload}
            disabled={downloading}
            aria-label={`Download ${artifact.name}`}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            {downloading ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Download className="size-3.5" aria-hidden />}
            Download
          </button>
        </div>
      ) : (
        <span className="shrink-0 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground" title="This file was not kept after training">
          Not stored
        </span>
      )}
    </li>
  );
}

export function VersionArtifactsPanel({ modelId, version }: { modelId: string; version: number }) {
  const artifacts = useVersionArtifacts(modelId, version);
  const download = useDownloadVersionArtifact();
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [viewing, setViewing] = useState<VersionArtifact | null>(null);
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

  if (artifacts.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Loading artifacts…
      </div>
    );
  }

  if (artifacts.error) return <p className="text-sm text-destructive">{errorMessage(artifacts.error)}</p>;

  if (items.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        No artifacts yet. Files appear here once the training run for this version finishes.
      </p>
    );
  }

  return (
    <div>
      <ul className="space-y-2">
        {items.map((artifact) => (
          <ArtifactRow
            key={artifact.name}
            artifact={artifact}
            downloading={downloading === artifact.name}
            onView={() => setViewing(artifact)}
            onDownload={() => handleDownload(artifact.name)}
          />
        ))}
      </ul>
      {downloadError ? <p className="mt-3 text-sm text-destructive">{downloadError}</p> : null}
      {viewing ? (
        <ArtifactPreviewDialog modelId={modelId} version={version} artifact={viewing} onClose={() => setViewing(null)} />
      ) : null}
    </div>
  );
}
