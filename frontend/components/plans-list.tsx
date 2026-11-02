"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { BookMarked, Eye, Globe2, Lock, Pencil, Play, Plus, Search, Trash2, User, Users, X } from "lucide-react";
import { useMemo, useState } from "react";

import { PlanFormDialog } from "@/components/plan-form-dialog";
import { PlanRunDialog } from "@/components/plan-run-dialog";
import { PlanViewDialog } from "@/components/plan-view-dialog";
import { Pill } from "@/components/models-ui";
import { useDeletePlan, usePlans } from "@/lib/queries";
import type { Plan } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "all" | "mine" | "shared";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "mine", label: "Mine" },
  { value: "shared", label: "Shared with me" },
];

export function PlansList() {
  const plans = usePlans();
  const deletePlan = useDeletePlan();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [editor, setEditor] = useState<{ plan: Plan | null } | null>(null);
  const [viewing, setViewing] = useState<Plan | null>(null);
  const [running, setRunning] = useState<Plan | null>(null);
  const [deleting, setDeleting] = useState<Plan | null>(null);

  const all = useMemo(() => plans.data ?? [], [plans.data]);
  const mineCount = all.filter((plan) => plan.is_owner).length;
  const counts: Record<Filter, number> = { all: all.length, mine: mineCount, shared: all.length - mineCount };

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return all.filter((plan) => {
      if (filter === "mine" && !plan.is_owner) return false;
      if (filter === "shared" && plan.is_owner) return false;
      if (!needle) return true;
      return plan.name.toLowerCase().includes(needle) || plan.description.toLowerCase().includes(needle);
    });
  }, [all, filter, query]);

  function confirmDelete() {
    if (!deleting) return;
    deletePlan.mutate(deleting.id, { onSuccess: () => setDeleting(null) });
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-6 md:p-10">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Plans</h1>
          <p className="text-sm text-muted-foreground">
            Saved training recipes. Running a plan always creates a new model.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setEditor({ plan: null })}
          className="inline-flex items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover"
        >
          <Plus className="size-4" aria-hidden />
          New plan
        </button>
      </header>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative w-full sm:max-w-xs">
          <span className="sr-only">Search plans</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search plans"
            className="h-9 w-full rounded-lg border border-border bg-card pl-9 pr-3 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/40"
          />
        </label>
        <div role="group" aria-label="Filter plans" className="inline-flex w-full rounded-lg border border-border bg-card p-1 sm:w-auto">
          {FILTERS.map((option) => {
            const active = filter === option.value;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(option.value)}
                className={cn(
                  "flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors sm:flex-none",
                  active ? "bg-primary text-white shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                {option.label}
                <span className={cn("ml-1.5 tabular-nums", active ? "text-white/80" : "text-muted-foreground")}>{counts[option.value]}</span>
              </button>
            );
          })}
        </div>
      </div>

      {plans.error ? <p className="text-sm text-destructive">{plans.error.message}</p> : null}

      {plans.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden>
          {[0, 1, 2].map((key) => (
            <div key={key} className="h-40 animate-pulse rounded-xl border border-border bg-card" />
          ))}
        </div>
      ) : null}

      {!plans.isLoading && all.length === 0 ? (
        <div className="flex min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-border p-12 text-center">
          <BookMarked className="mb-3 size-8 text-muted-foreground" aria-hidden />
          <p className="text-sm font-medium">No plans yet</p>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Create a plan from a training recipe you reuse. Plans you share with the organisation show up here for everyone.
          </p>
        </div>
      ) : null}

      {!plans.isLoading && all.length > 0 && visible.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted-foreground">No plans match these filters.</p>
      ) : null}

      {visible.length > 0 ? (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((plan) => (
            <li
              key={plan.id}
              className="group flex flex-col rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold" title={plan.name}>
                    {plan.name}
                  </h2>
                  <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">
                    {plan.description || "No description"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => setViewing(plan)}
                    className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    aria-label={`View ${plan.name}`}
                  >
                    <Eye className="size-4" />
                  </button>
                  {plan.is_owner ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setEditor({ plan })}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                        aria-label={`Edit ${plan.name}`}
                      >
                        <Pencil className="size-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          deletePlan.reset();
                          setDeleting(plan);
                        }}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-red-500/10 hover:text-red-600"
                        aria-label={`Delete ${plan.name}`}
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                {plan.visibility === "org" ? (
                  <Pill tone="bg-teal/15 text-teal ring-teal/30">
                    <Globe2 className="size-3" aria-hidden />
                    Organisation
                  </Pill>
                ) : (
                  <Pill tone="bg-muted text-muted-foreground ring-border">
                    <Lock className="size-3" aria-hidden />
                    Private
                  </Pill>
                )}
                <Pill tone="bg-primary/10 text-primary ring-primary/30">
                  {plan.is_owner ? <User className="size-3" aria-hidden /> : <Users className="size-3" aria-hidden />}
                  {plan.is_owner ? "You" : plan.owner_email ?? "Shared"}
                </Pill>
              </div>

              <div className="mt-auto flex justify-end pt-5">
                <button
                  type="button"
                  onClick={() => setRunning(plan)}
                  className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm font-medium transition-colors hover:border-primary hover:text-primary"
                >
                  <Play className="size-4" aria-hidden />
                  Run as new model
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {editor ? <PlanFormDialog plan={editor.plan} onOpenChange={(open) => !open && setEditor(null)} /> : null}
      {viewing ? (
        <PlanViewDialog
          plan={viewing}
          onOpenChange={(open) => !open && setViewing(null)}
          onEdit={(plan) => {
            setViewing(null);
            setEditor({ plan });
          }}
        />
      ) : null}

      {running ? <PlanRunDialog plan={running} onOpenChange={(open) => !open && setRunning(null)} /> : null}

      {deleting ? (
        <Dialog.Root open onOpenChange={(open) => !open && setDeleting(null)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
            <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,26rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
              <div className="flex items-start justify-between gap-4">
                <Dialog.Title className="text-lg font-semibold">Delete “{deleting.name}”?</Dialog.Title>
                <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
                  <X className="size-4" />
                </Dialog.Close>
              </div>
              <Dialog.Description className="mt-2 text-sm text-muted-foreground">
                The plan is removed for everyone it is shared with. Models it already created are kept.
              </Dialog.Description>
              {deletePlan.error ? (
                <p role="alert" className="mt-3 text-sm text-destructive">
                  {deletePlan.error.message}
                </p>
              ) : null}
              <div className="mt-6 flex justify-end gap-2">
                <Dialog.Close className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Cancel</Dialog.Close>
                <button
                  type="button"
                  onClick={confirmDelete}
                  disabled={deletePlan.isPending}
                  className="inline-flex items-center gap-2 rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 disabled:pointer-events-none disabled:opacity-50"
                >
                  <Trash2 className="size-4" aria-hidden />
                  {deletePlan.isPending ? "Deleting…" : "Delete plan"}
                </button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      ) : null}
    </div>
  );
}
