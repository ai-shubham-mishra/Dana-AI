"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { FileText, Globe2, Lock, Pencil, X } from "lucide-react";

import { Markdown } from "@/components/markdown";
import type { Plan } from "@/lib/types";

export function PlanViewDialog({
  plan,
  onOpenChange,
  onEdit,
}: {
  plan: Plan;
  onOpenChange: (open: boolean) => void;
  onEdit: (plan: Plan) => void;
}) {
  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90dvh] w-[min(94vw,44rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <Dialog.Title className="flex items-center gap-2 truncate text-lg font-semibold" title={plan.name}>
                <FileText className="size-4 shrink-0 text-primary" aria-hidden />
                {plan.name}
              </Dialog.Title>
              <Dialog.Description className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                {plan.visibility === "org" ? <Globe2 className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
                {plan.visibility === "org" ? "Shared with the organisation" : "Only you"}
                {plan.description ? <span>· {plan.description}</span> : null}
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <div className="mt-5 min-h-0 flex-1 overflow-y-auto rounded-lg border border-border bg-background p-4">
            <Markdown>{plan.content}</Markdown>
          </div>

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Close</Dialog.Close>
            {plan.is_owner ? (
              <button
                type="button"
                onClick={() => onEdit(plan)}
                className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-medium transition-colors hover:border-primary hover:text-primary"
              >
                <Pencil className="size-4" aria-hidden />
                Edit plan
              </button>
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
