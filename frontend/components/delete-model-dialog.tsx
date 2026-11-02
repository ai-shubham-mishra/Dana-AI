"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Loader2, Trash2, X } from "lucide-react";
import { useState } from "react";

import type { Deployment } from "@/lib/types";
import { cn } from "@/lib/utils";

export function DeleteModelDialog({
  title,
  description,
  confirmLabel,
  containers,
  pending,
  error,
  onConfirm,
  onOpenChange,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  containers: Deployment[];
  pending: boolean;
  error: string | null;
  onConfirm: (deallocate: boolean) => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [stopContainers, setStopContainers] = useState(false);
  const needsStop = containers.length > 0;
  const blocked = pending || (needsStop && !stopContainers);

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-[min(92vw,32rem)] -translate-x-1/2 -translate-y-1/2 flex-col gap-5 overflow-y-auto rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-destructive/10 text-destructive">
                <Trash2 className="size-4" aria-hidden />
              </span>
              <div>
                <Dialog.Title className="text-lg font-semibold">{title}</Dialog.Title>
                <Dialog.Description className="mt-1.5 text-sm text-muted-foreground">{description}</Dialog.Description>
              </div>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          {needsStop ? (
            <div className="space-y-3">
              <ul className="space-y-1.5 rounded-lg border border-border bg-muted/40 p-3">
                {containers.map((container) => (
                  <li key={container.id} className="flex items-center justify-between gap-3 text-xs">
                    <span className="truncate font-mono">{container.container}</span>
                    <span className="shrink-0 text-muted-foreground">port {container.host_port}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                role="switch"
                aria-checked={stopContainers}
                onClick={() => setStopContainers((value) => !value)}
                className="flex w-full items-center justify-between gap-4 rounded-lg border border-border p-3 text-left text-sm outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring/50"
              >
                <span className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" aria-hidden />
                  <span>
                    Stop {containers.length === 1 ? "this running container" : `these ${containers.length} running containers`}{" "}
                    first
                  </span>
                </span>
                <span
                  aria-hidden
                  className={cn(
                    "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
                    stopContainers ? "bg-destructive" : "bg-muted-foreground/30",
                  )}
                >
                  <span
                    className={cn(
                      "inline-block size-5 rounded-full bg-white shadow transition-transform",
                      stopContainers ? "translate-x-5" : "translate-x-0.5",
                    )}
                  />
                </span>
              </button>
            </div>
          ) : null}

          <p className="text-xs text-muted-foreground">
            Deleted items are archived for 7 days before they are purged. Their names stay reserved until then.
          </p>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}

          <div className="flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
            <button
              type="button"
              onClick={() => onConfirm(needsStop)}
              disabled={blocked}
              className="inline-flex items-center gap-2 rounded-md bg-destructive px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {confirmLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
