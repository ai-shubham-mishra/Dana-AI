"use client";

import type { Plan } from "@/lib/types";
import { cn } from "@/lib/utils";

const CATALOG_WORD = "plans";

export type SlashOption = {
  key: string;
  slug: string;
  name: string;
  detail: string;
  badge: string | null;
};

export function slashQuery(draft: string): string | null {
  return /^\/[a-z0-9-]*$/i.test(draft) ? draft.slice(1).toLowerCase() : null;
}

// Typing a prefix of "plans" (including "/" alone) lists every plan, like DeepAgent's /workflow typeahead; other text filters.
export function slashOptions(plans: Plan[], query: string): SlashOption[] {
  const showAll = CATALOG_WORD.startsWith(query);
  return plans
    .filter((plan) => showAll || plan.slug.includes(query) || plan.name.toLowerCase().includes(query))
    .map((plan) => {
      const kpi = typeof plan.spec.kpi === "string" ? plan.spec.kpi : "";
      const channels = Array.isArray(plan.spec.channels) ? plan.spec.channels.join(", ") : "";
      return {
        key: plan.id,
        slug: plan.slug,
        name: plan.name,
        detail: [kpi && `KPI ${kpi}`, channels].filter(Boolean).join(" · "),
        badge: plan.is_owner ? (plan.visibility === "org" ? "Shared" : "Private") : `By ${plan.owner_email ?? "a teammate"}`,
      };
    });
}

export function PlanSlashMenu({
  id,
  options,
  activeIndex,
  query,
  totalPlans,
  onHover,
  onPick,
}: {
  id: string;
  options: SlashOption[];
  activeIndex: number;
  query: string;
  totalPlans: number;
  onHover: (index: number) => void;
  onPick: (option: SlashOption) => void;
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
            : `No plan matches /${query}.`}
        </p>
      ) : (
        options.map((option, index) => (
          <button
            key={option.key}
            id={`${id}-${index}`}
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            onMouseDown={(event) => event.preventDefault()}
            onMouseEnter={() => onHover(index)}
            onClick={() => onPick(option)}
            className={cn(
              "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors",
              index === activeIndex ? "bg-magenta-wash" : "hover:bg-muted"
            )}
          >
            <span className="shrink-0 font-mono text-sm font-medium">/{option.slug}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{option.name}</span>
              {option.detail && <span className="block truncate text-xs text-muted-foreground">{option.detail}</span>}
            </span>
            {option.badge && (
              <span className="shrink-0 rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                {option.badge}
              </span>
            )}
          </button>
        ))
      )}
    </div>
  );
}
