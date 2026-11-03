"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, X } from "lucide-react";

import { formatBytes, formatPreviewText } from "@/lib/artifact-preview";
import { useVersionArtifactText } from "@/lib/queries";
import type { VersionArtifact } from "@/lib/types";

export function ArtifactPreviewDialog({
  modelId,
  version,
  artifact,
  onClose,
}: {
  modelId: string;
  version: number;
  artifact: VersionArtifact;
  onClose: () => void;
}) {
  const content = useVersionArtifactText(modelId, version, artifact.name, true);

  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex h-[min(80vh,40rem)] w-[min(96vw,56rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border border-border bg-card text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="truncate font-mono text-base font-semibold">{artifact.name}</Dialog.Title>
              <Dialog.Description className="mt-0.5 text-xs tabular-nums text-muted-foreground">
                {formatBytes(artifact.bytes)}
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" aria-hidden />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-auto bg-muted/40">
            {content.isLoading ? (
              <div className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading file…
              </div>
            ) : content.error ? (
              <p className="p-5 text-sm text-destructive">{content.error.message}</p>
            ) : (
              <pre className="whitespace-pre p-5 font-mono text-xs leading-relaxed">
                {formatPreviewText(artifact.name, content.data ?? "")}
              </pre>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
