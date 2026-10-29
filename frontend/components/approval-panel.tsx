"use client";

import { useState } from "react";
import { Check, Pencil, Reply, ShieldAlert, X, type LucideIcon } from "lucide-react";

import type { Decision, DecisionType, PendingAction, PendingApproval } from "@/lib/types";

type Draft = { choice: DecisionType | null; message: string; argsText: string };

const LABELS: Record<DecisionType, string> = { approve: "Approve", edit: "Edit", reject: "Reject", respond: "Answer" };
const ICONS: Record<DecisionType, LucideIcon> = { approve: Check, edit: Pencil, reject: X, respond: Reply };
const FIELD =
  "w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-50";

function initialDraft(action: PendingAction): Draft {
  const choice = action.allowed_decisions.length === 1 ? action.allowed_decisions[0] : null;
  return { choice, message: "", argsText: JSON.stringify(action.args, null, 2) };
}

function parseArgs(text: string): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(text);
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function optionsOf(action: PendingAction): string[] {
  const options = action.name === "ask_user" ? action.args.options : undefined;
  return Array.isArray(options) ? options.filter((option): option is string => typeof option === "string") : [];
}

function formatValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export function buildDecisions(actions: PendingAction[], drafts: Draft[]): Decision[] | null {
  const decisions: Decision[] = [];
  for (const [index, action] of actions.entries()) {
    const draft = drafts[index];
    const message = draft?.message.trim() ?? "";
    if (!draft?.choice) return null;
    if (draft.choice === "approve") {
      decisions.push({ type: "approve" });
    } else if (draft.choice === "reject") {
      decisions.push(message ? { type: "reject", message } : { type: "reject" });
    } else if (draft.choice === "respond") {
      if (!message) return null;
      decisions.push({ type: "respond", message });
    } else {
      const args = parseArgs(draft.argsText);
      if (!args) return null;
      decisions.push({ type: "edit", edited_action: { name: action.name, args } });
    }
  }
  return decisions;
}

function ApprovalCard({
  action,
  draft,
  disabled,
  onChange,
}: {
  action: PendingAction;
  draft: Draft;
  disabled: boolean;
  onChange: (patch: Partial<Draft>) => void;
}) {
  const options = optionsOf(action);
  const details = action.name === "ask_user" ? [] : Object.entries(action.args);
  const argsError = draft.choice === "edit" && !parseArgs(draft.argsText) ? "Edited arguments must be a JSON object." : null;

  return (
    <div className="rounded-xl border border-border bg-background p-3">
      <p className="text-sm font-medium">
        {action.name === "ask_user" ? String(action.args.question ?? action.description) : action.description}
      </p>
      {details.length > 0 && (
        <dl className="mt-2 space-y-1 text-xs">
          {details.map(([key, value]) => (
            <div key={key} className="flex gap-2">
              <dt className="shrink-0 text-muted-foreground">{key}</dt>
              <dd className="min-w-0 break-all">{formatValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}

      {action.allowed_decisions.length > 1 && (
        <div role="group" aria-label="Decision" className="mt-3 flex flex-wrap gap-2">
          {action.allowed_decisions.map((type) => {
            const Icon = ICONS[type];
            const selected = draft.choice === type;
            return (
              <button
                key={type}
                type="button"
                disabled={disabled}
                aria-pressed={selected}
                onClick={() => onChange({ choice: type })}
                className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                  selected ? "border-cta bg-cta text-cta-foreground" : "border-border bg-card hover:bg-muted"
                }`}
              >
                <Icon className="size-3.5" />
                {LABELS[type]}
              </button>
            );
          })}
        </div>
      )}

      {draft.choice === "respond" && action.allowed_decisions.includes("respond") && options.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {options.map((option) => (
            <button
              key={option}
              type="button"
              disabled={disabled}
              onClick={() => onChange({ message: option })}
              className="rounded-full border border-border bg-card px-3 py-1 text-xs transition-colors hover:bg-muted disabled:opacity-50"
            >
              {option}
            </button>
          ))}
        </div>
      )}

      {draft.choice === "respond" && (
        <textarea
          aria-label="Your answer"
          value={draft.message}
          disabled={disabled}
          rows={2}
          placeholder="Type your answer…"
          onChange={(event) => onChange({ message: event.target.value })}
          className={`${FIELD} mt-3`}
        />
      )}
      {draft.choice === "reject" && (
        <textarea
          aria-label="Reason"
          value={draft.message}
          disabled={disabled}
          rows={2}
          placeholder="Reason (optional)"
          onChange={(event) => onChange({ message: event.target.value })}
          className={`${FIELD} mt-3`}
        />
      )}
      {draft.choice === "edit" && (
        <>
          <textarea
            aria-label="Edited arguments"
            value={draft.argsText}
            disabled={disabled}
            rows={6}
            onChange={(event) => onChange({ argsText: event.target.value })}
            className={`${FIELD} mt-3 font-mono text-xs`}
          />
          {argsError && <p className="mt-1 text-xs text-destructive">{argsError}</p>}
        </>
      )}
    </div>
  );
}

export function ApprovalPanel({
  pending,
  disabled,
  onSubmit,
}: {
  pending: PendingApproval;
  disabled: boolean;
  onSubmit: (decisions: Decision[]) => void;
}) {
  const [drafts, setDrafts] = useState<Draft[]>(() => pending.actions.map(initialDraft));
  const decisions = buildDecisions(pending.actions, drafts);

  function update(index: number, patch: Partial<Draft>) {
    setDrafts((current) => current.map((draft, i) => (i === index ? { ...draft, ...patch } : draft)));
  }

  return (
    <section aria-label="Approval required" className="rounded-2xl border border-primary/40 bg-card p-4 shadow-elevated">
      <header className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <ShieldAlert className="size-4 text-primary" />
        Dana needs your input to continue
      </header>
      <div className="space-y-3">
        {pending.actions.map((action, index) => (
          <ApprovalCard
            key={`${index}-${action.name}`}
            action={action}
            draft={drafts[index] ?? initialDraft(action)}
            disabled={disabled}
            onChange={(patch) => update(index, patch)}
          />
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          disabled={disabled || !decisions}
          onClick={() => decisions && onSubmit(decisions)}
          className="inline-flex items-center gap-1.5 rounded-md bg-cta px-4 py-1.5 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          Submit
        </button>
      </div>
    </section>
  );
}
