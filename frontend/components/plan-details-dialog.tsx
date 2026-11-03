"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Globe2, Info, Lock, User, Users, X } from "lucide-react";
import type { ReactNode } from "react";

import type { Plan } from "@/lib/types";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function PlanDetailsDialog({ plan, onOpenChange }: { plan: Plan; onOpenChange: (open: boolean) => void }) {
  const rows: { label: string; value: ReactNode }[] = [
    { label: "Slug", value: <span className="font-mono">/{plan.slug}</span> },
    {
      label: "Owner",
      value: (
        <span className="inline-flex items-center gap-1.5">
          {plan.is_owner ? <User className="size-3.5" aria-hidden /> : <Users className="size-3.5" aria-hidden />}
          {plan.is_owner ? "You" : plan.owner_email ?? "Unknown"}
        </span>
      ),
    },
    {
      label: "Visibility",
      value: (
        <span className="inline-flex items-center gap-1.5">
          {plan.visibility === "org" ? <Globe2 className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
          {plan.visibility === "org" ? "Organisation" : "Private"}
        </span>
      ),
    },
    { label: "Created", value: formatTimestamp(plan.created_at) },
    { label: "Last updated", value: formatTimestamp(plan.updated_at) },
  ];

  return (
    <Dialog.Root open onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,26rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="flex min-w-0 items-center gap-2 truncate text-lg font-semibold" title={plan.name}>
              <Info className="size-4 shrink-0 text-primary" aria-hidden />
              <span className="truncate">{plan.name}</span>
            </Dialog.Title>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">Plan details</Dialog.Description>
          <dl className="mt-5 divide-y divide-border rounded-lg border border-border text-sm">
            {rows.map((row) => (
              <div key={row.label} className="grid grid-cols-[7rem_1fr] gap-3 px-4 py-2.5">
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd className="min-w-0 break-words">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
