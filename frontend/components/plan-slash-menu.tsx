"use client";

import { Eye } from "lucide-react";

import type { Plan } from "@/lib/types";
import { cn } from "@/lib/utils";

export type SlashOption = {
  key: string;
  slug: string;
  plan: Plan;
};

// The picker opens only once "/plans" is typed in full; text after it filters the list (like DeepAgent's /workflow).
const PICKER_PATTERN = /^\/plans(?:\s+(\S*))?$/i;

export function slashQuery(draft: string): string | null {
  const match = PICKER_PATTERN.exec(draft);
  return match ? (match[1] ?? "").toLowerCase() : null;
}

export function slashOptions(plans: Plan[], query: string): SlashOption[] {
  return plans
    .filter((plan) => !query || plan.slug.includes(query) || plan.name.toLowerCase().includes(query))
    .map((plan) => ({ key: plan.id, slug: plan.slug, plan }));
}

export function PlanSlashMenu({
  id,
  options,
  activeIndex,
  query,
  totalPlans,
  onHover,
  onPick,
  onPreview,
}: {
  id: string;
  options: SlashOption[];
  activeIndex: number;
  query: string;
  totalPlans: number;
  onHover: (index: number) => void;
  onPick: (option: SlashOption) => void;
  onPreview: (plan: Plan) => void;
}) {
  return (
    <div
      id={id}
      role="listbox"
      aria-label="Saved plans"
      className="absolute inset-x-0 bottom-full z-20 mb-2 max-h-72 overflow-y-auto rounded-xl border border-border bg-card p-1.5 shadow-elevated"
    >
      {options.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted-foreground">
          {totalPlans === 0
            ? "No plans saved yet. Create one on the Plans page."
            : `No plan matches "${query}".`}
        </p>
      ) : (
        options.map((option, index) => (
          <div
            key={option.key}
            id={`${id}-${index}`}
            role="option"
            aria-selected={index === activeIndex}
            onMouseDown={(event) => event.preventDefault()}
            onMouseEnter={() => onHover(index)}
            onClick={() => onPick(option)}
            className={cn(
              "flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 transition-colors",
              index === activeIndex ? "bg-magenta-wash" : "hover:bg-muted"
            )}
          >
            <span className="min-w-0 truncate font-mono text-sm font-medium">/{option.slug}</span>
            <button
              type="button"
              tabIndex={-1}
              aria-label={`Preview ${option.plan.name}`}
              onMouseDown={(event) => event.preventDefault()}
              onClick={(event) => {
                event.stopPropagation();
                onPreview(option.plan);
              }}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              <Eye className="size-3.5" aria-hidden />
              Preview
            </button>
          </div>
        ))
      )}
    </div>
  );
}
