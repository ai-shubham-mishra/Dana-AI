"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Play, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useRunPlan } from "@/lib/queries";
import type { ApiError } from "@/lib/api";
import type { Plan, PlanNameConflict } from "@/lib/types";
import { cn } from "@/lib/utils";

function isNameConflict(error: ApiError | null): error is ApiError & { detail: PlanNameConflict } {
  return error?.status === 409 && error.detail?.code === "name_taken";
}

export function PlanRunDialog({ plan, onOpenChange }: { plan: Plan; onOpenChange: (open: boolean) => void }) {
  const router = useRouter();
  const run = useRunPlan();
  const [modelName, setModelName] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const error = run.error;
  const conflict = isNameConflict(error) ? error.detail : null;
  const suggestions = conflict && Array.isArray(conflict.suggestions) ? conflict.suggestions : [];

  function submit() {
    setLocalError(null);
    const trimmed = modelName.trim();
    if (!trimmed) {
      setLocalError("Enter a name for the new model.");
      return;
    }
    run.mutate(
      { planId: plan.id, modelName: trimmed },
      {
        onSuccess: () => {
          onOpenChange(false);
          router.push("/jobs");
        },
      },
    );
  }

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Run “{plan.name}”</Dialog.Title>
              <Dialog.Description className="mt-2 text-sm text-muted-foreground">
                This plan trains a brand-new model with the saved settings. It never adds a version to an existing model.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <label className="mt-5 block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">New model name</span>
            <input
              value={modelName}
              onChange={(event) => setModelName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") submit();
              }}
              autoFocus
              placeholder="e.g. weekly-revenue-q3"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40"
            />
          </label>

          {conflict ? (
            <div role="alert" className="mt-3 space-y-2 rounded-lg border border-amber-400/40 bg-amber-400/10 p-3">
              <p className="text-sm text-amber-700 dark:text-amber-300">
                A model named “{conflict.name}” already exists. Pick one of these instead:
              </p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setModelName(suggestion)}
                    className={cn(
                      "rounded-full border border-border bg-card px-2.5 py-1 font-mono text-xs transition-colors hover:border-primary hover:text-primary",
                      modelName === suggestion && "border-primary text-primary",
                    )}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {localError || (error && !conflict) ? (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {localError ?? error?.message}
            </p>
          ) : null}

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
            <button
              type="button"
              onClick={submit}
              disabled={run.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:pointer-events-none disabled:opacity-50"
            >
              <Play className="size-4" aria-hidden />
              {run.isPending ? "Queuing…" : "Start training"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
