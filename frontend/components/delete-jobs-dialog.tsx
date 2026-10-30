"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, X } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

export function DeleteJobsDialog({
  count,
  pending,
  error,
  onConfirm,
  onOpenChange,
}: {
  count: number;
  pending: boolean;
  error: string | null;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const noun = count === 1 ? "job" : "jobs";

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Delete {count} training {noun}?</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-muted-foreground">
                This permanently removes each job&apos;s history, its run folder (training script, config, dataset and logs)
                and the saved model artifact. Jobs that are still running are skipped. This cannot be undone.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={confirmed}
            onClick={() => setConfirmed((value) => !value)}
            className="mt-5 flex w-full items-center justify-between gap-4 rounded-lg border border-border p-3 text-left text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <span>I understand this permanently deletes the selected {noun} and their files.</span>
            <span
              aria-hidden
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
                confirmed ? "bg-destructive" : "bg-muted-foreground/30",
              )}
            >
              <span
                className={cn(
                  "inline-block size-5 rounded-full bg-white shadow transition-transform",
                  confirmed ? "translate-x-5" : "translate-x-0.5",
                )}
              />
            </span>
          </button>

          {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
            <button
              type="button"
              onClick={onConfirm}
              disabled={!confirmed || pending}
              className="inline-flex items-center gap-2 rounded-md bg-destructive px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-destructive/90 disabled:pointer-events-none disabled:opacity-40"
            >
              <Trash2 className="size-4" aria-hidden />
              {pending ? "Deleting…" : `Delete ${noun}`}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
