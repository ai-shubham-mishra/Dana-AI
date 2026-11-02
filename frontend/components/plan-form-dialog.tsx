"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Globe2, Lock, X } from "lucide-react";
import { useState } from "react";

import { useCreatePlan, useUpdatePlan } from "@/lib/queries";
import type { Plan, PlanInput, PlanSpec, PlanVisibility } from "@/lib/types";
import { cn } from "@/lib/utils";

const SPEC_TEMPLATE: PlanSpec = {
  kpi: "revenue",
  channels: ["tv_spend", "search_spend"],
  controls: [],
  sources: [
    {
      table: "your_table",
      date_column: "date",
      metrics: { revenue: "revenue", tv_spend: "tv_spend", search_spend: "search_spend" },
      filters: {},
    },
  ],
  date_start: "2024-01-01",
  date_end: "2024-12-31",
  overrides: {},
  preparation: { date_features: ["month"] },
};

const INPUT_CLASS =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40";

export function PlanFormDialog({
  plan,
  onOpenChange,
}: {
  plan: Plan | null;
  onOpenChange: (open: boolean) => void;
}) {
  const isEdit = plan !== null;
  const create = useCreatePlan();
  const update = useUpdatePlan();
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [visibility, setVisibility] = useState<PlanVisibility>(plan?.visibility ?? "private");
  const [specText, setSpecText] = useState(() => JSON.stringify(plan?.spec ?? SPEC_TEMPLATE, null, 2));
  const [localError, setLocalError] = useState<string | null>(null);

  const pending = create.isPending || update.isPending;
  const serverError = create.error ?? update.error;

  function submit() {
    setLocalError(null);
    if (!name.trim()) {
      setLocalError("Give the plan a name.");
      return;
    }
    let spec: PlanSpec;
    try {
      const parsed: unknown = JSON.parse(specText);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("The spec must be a JSON object.");
      spec = parsed as PlanSpec;
    } catch (error) {
      setLocalError(`Spec is not valid JSON: ${error instanceof Error ? error.message : "unknown error"}`);
      return;
    }
    const input: PlanInput = { name: name.trim(), description: description.trim(), visibility, spec };
    const onSuccess = () => onOpenChange(false);
    if (plan) {
      update.mutate({ planId: plan.id, changes: input }, { onSuccess });
    } else {
      create.mutate(input, { onSuccess });
    }
  }

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[90dvh] w-[min(94vw,44rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">{isEdit ? "Edit plan" : "New plan"}</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                A plan is a reusable training recipe. Running it always creates a new model.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <div className="mt-5 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Name</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={80}
                  placeholder="Weekly revenue baseline"
                  className={INPUT_CLASS}
                />
              </label>
              <label className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">Description</span>
                <input
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What this recipe is for"
                  className={INPUT_CLASS}
                />
              </label>
            </div>

            <div className="space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">Visibility</span>
              <div role="group" aria-label="Visibility" className="inline-flex rounded-lg border border-border bg-background p-1">
                {(
                  [
                    { value: "private", label: "Only me", icon: Lock },
                    { value: "org", label: "Whole organisation", icon: Globe2 },
                  ] as const
                ).map((option) => {
                  const active = visibility === option.value;
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setVisibility(option.value)}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                        active ? "bg-primary text-white shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon className="size-3.5" aria-hidden />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">Spec (JSON)</span>
              <textarea
                value={specText}
                onChange={(event) => setSpecText(event.target.value)}
                spellCheck={false}
                rows={16}
                className={cn(INPUT_CLASS, "font-mono text-xs leading-relaxed")}
              />
              <span className="block text-xs text-muted-foreground">
                Replace <code>your_table</code> and the column names with your connector tables. The server checks the spec when you save.
              </span>
            </label>
          </div>

          {localError || serverError ? (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {localError ?? serverError?.message}
            </p>
          ) : null}

          <div className="mt-6 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
            <button
              type="button"
              onClick={submit}
              disabled={pending}
              className="inline-flex items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:pointer-events-none disabled:opacity-50"
            >
              {pending ? "Saving…" : isEdit ? "Save changes" : "Create plan"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
