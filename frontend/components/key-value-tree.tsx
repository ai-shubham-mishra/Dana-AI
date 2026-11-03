"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

type Nested = Record<string, unknown> | unknown[];

function isNested(value: unknown): value is Nested {
  return value !== null && typeof value === "object";
}

function entriesOf(value: Nested): [string, unknown][] {
  return Array.isArray(value) ? value.map((item, index) => [`#${index + 1}`, item]) : Object.entries(value);
}

function Leaf({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">—</span>;
  if (typeof value === "number") return <span>{Number.isInteger(value) ? String(value) : value.toFixed(4)}</span>;
  if (typeof value === "boolean") return <span>{value ? "true" : "false"}</span>;
  return <span className="break-all">{String(value)}</span>;
}

// Nested nodes start open only at the top level; deeper levels stay collapsed until expanded.
function TreeNode({ label, value, depth }: { label: string; value: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 1);

  if (!isNested(value) || entriesOf(value).length === 0) {
    return (
      <li className="flex min-w-0 gap-3 py-1 pl-5 text-sm">
        <span className="shrink-0 text-muted-foreground">{label}</span>
        <span className="min-w-0 font-mono text-xs leading-5">
          <Leaf value={isNested(value) ? null : value} />
        </span>
      </li>
    );
  }

  const children = entriesOf(value);
  const noun = Array.isArray(value) ? "items" : "fields";
  return (
    <li className="text-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="flex w-full min-w-0 items-center gap-1.5 rounded-md py-1 text-left hover:bg-muted/60"
      >
        <ChevronRight className={cn("size-3.5 shrink-0 text-muted-foreground transition-transform duration-200", open && "rotate-90")} aria-hidden />
        <span className="min-w-0 truncate font-medium">{label}</span>
        <span className="ml-auto shrink-0 pl-3 text-xs tabular-nums text-muted-foreground">
          {children.length} {noun}
        </span>
      </button>
      {open ? (
        <ul className="ml-[7px] space-y-0.5 border-l border-border pl-2">
          {children.map(([key, child]) => (
            <TreeNode key={key} label={key} value={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function KeyValueTree({ data }: { data: unknown }) {
  if (!isNested(data) || entriesOf(data).length === 0) {
    return (
      <span className="font-mono text-xs">
        <Leaf value={isNested(data) ? null : data} />
      </span>
    );
  }
  return (
    <ul className="space-y-0.5">
      {entriesOf(data).map(([key, value]) => (
        <TreeNode key={key} label={key} value={value} depth={0} />
      ))}
    </ul>
  );
}
