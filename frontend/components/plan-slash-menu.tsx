"use client";

import type { Plan } from "@/lib/types";
import { cn } from "@/lib/utils";

const LIST_COMMAND = "plans";
const COMMAND_WORDS = ["/plan", "/plans"];

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

export function isSlashCommandWord(draft: string): boolean {
  return COMMAND_WORDS.includes(draft.trim().toLowerCase());
}

export function slashOptions(plans: Plan[], query: string): SlashOption[] {
  const options: SlashOption[] = [];
  if (LIST_COMMAND.startsWith(query)) {
    options.push({
      key: "list",
      slug: LIST_COMMAND,
      name: "List all plans",
      detail: "Show every saved plan in the chat",
      badge: null,
    });
  }
  for (const plan of plans) {
    if (query && !plan.slug.includes(query) && !plan.name.toLowerCase().includes(query)) continue;
    const kpi = typeof plan.spec.kpi === "string" ? plan.spec.kpi : "";
    const channels = Array.isArray(plan.spec.channels) ? plan.spec.channels.join(", ") : "";
    options.push({
      key: plan.id,
      slug: plan.slug,
      name: plan.name,
      detail: [kpi && `KPI ${kpi}`, channels].filter(Boolean).join(" · "),
      badge: plan.is_owner
        ? plan.visibility === "org"
          ? "Shared"
          : "Private"
        : `By ${plan.owner_email ?? "a teammate"}`,
    });
  }
  return options;
}

export function PlanSlashMenu({
  id,
  options,
  activeIndex,
  query,
  onHover,
  onPick,
}: {
  id: string;
  options: SlashOption[];
  activeIndex: number;
  query: string;
  onHover: (index: number) => void;
  onPick: (option: SlashOption) => void;
}) {
  return (
    <div
      id={id}
      role="listbox"
      aria-label="Commands and saved plans"
      className="absolute inset-x-0 bottom-full z-20 mb-2 max-h-72 overflow-y-auto rounded-xl border border-border bg-card p-1.5 shadow-elevated"
    >
      {options.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted-foreground">
          No command or plan matches /{query}. Create plans on the Plans page.
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
