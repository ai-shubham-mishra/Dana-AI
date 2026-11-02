"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { RefreshCw, X } from "lucide-react";

import { KeyValueTree } from "@/components/key-value-tree";
import type { ModelVersion } from "@/lib/types";

export function RetrainDialog({
  modelName,
  version,
  pending,
  error,
  onConfirm,
  onOpenChange,
}: {
  modelName: string;
  version: ModelVersion;
  pending: boolean;
  error: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[85dvh] w-[min(92vw,36rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">
                Retrain {modelName} from v{version.version}?
              </Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-muted-foreground">
                A new training job will run with the configuration below and be saved as the next version of this model.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <div className="mt-5 min-h-0 flex-1 overflow-y-auto rounded-lg border border-border bg-muted/30 p-4">
            <KeyValueTree data={version.params ?? {}} />
          </div>

          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={pending}
              className="inline-flex items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:pointer-events-none disabled:opacity-50"
            >
              <RefreshCw className={pending ? "size-4 animate-spin" : "size-4"} aria-hidden />
              {pending ? "Queuing…" : "Start retraining"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
