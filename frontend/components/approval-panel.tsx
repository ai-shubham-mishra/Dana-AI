"use client";

import { useState } from "react";
import { Check, Pencil, Reply, ShieldAlert, X, type LucideIcon } from "lucide-react";

import { KeyValueBoxes } from "@/components/key-value";
import { Markdown } from "@/components/markdown";
import type { Decision, DecisionType, PendingAction, PendingApproval } from "@/lib/types";

type ResponseType = "single_select" | "multi_select" | "text" | "number" | "boolean";
type Draft = { choice: DecisionType | null; message: string; value: unknown; argsText: string };

const LABELS: Record<DecisionType, string> = { approve: "Approve", edit: "Edit", reject: "Reject", respond: "Answer" };
const ICONS: Record<DecisionType, LucideIcon> = { approve: Check, edit: Pencil, reject: X, respond: Reply };
const FIELD =
  "w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary disabled:opacity-50";
const CHIP =
  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50";

function initialDraft(action: PendingAction): Draft {
  const choice = action.allowed_decisions.length === 1 ? action.allowed_decisions[0] : null;
  return { choice, message: "", value: undefined, argsText: JSON.stringify(action.args, null, 2) };
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

function responseTypeOf(action: PendingAction): ResponseType {
  const declared = action.args.response_type;
  const type: ResponseType =
    declared === "single_select" || declared === "multi_select" || declared === "number" || declared === "boolean"
      ? declared
      : "text";
  return (type === "single_select" || type === "multi_select") && optionsOf(action).length === 0 ? "text" : type;
}

function answerFor(action: PendingAction, draft: Draft): Decision | null {
  const type = responseTypeOf(action);
  const options = optionsOf(action);
  if (type === "text") {
    const message = draft.message.trim();
    return message ? { type: "respond", message } : null;
  }
  if (type === "single_select") {
    return typeof draft.value === "string" && options.includes(draft.value) ? { type: "respond", value: draft.value } : null;
  }
  if (type === "multi_select") {
    const picked = Array.isArray(draft.value) ? draft.value : [];
    const valid = picked.length > 0 && picked.every((item) => typeof item === "string" && options.includes(item));
    return valid ? { type: "respond", value: picked } : null;
  }
  if (type === "number") {
    const number = Number(draft.message);
    return draft.message.trim() && Number.isFinite(number) ? { type: "respond", value: number } : null;
  }
  return typeof draft.value === "boolean" ? { type: "respond", value: draft.value } : null;
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
      const answer = answerFor(action, draft);
      if (!answer) return null;
      decisions.push(answer);
    } else {
      const args = parseArgs(draft.argsText);
      if (!args) return null;
      decisions.push({ type: "edit", edited_action: { name: action.name, args } });
    }
  }
  return decisions;
}

function AnswerInput({
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
  const type = responseTypeOf(action);
  const options = optionsOf(action);
  const picked = Array.isArray(draft.value) ? (draft.value as string[]) : [];

  if (type === "single_select" || type === "multi_select") {
    return (
      <div role="group" aria-label="Your answer" className="mt-3 flex flex-wrap gap-2">
        {options.map((option) => {
          const selected = type === "single_select" ? draft.value === option : picked.includes(option);
          return (
            <button
              key={option}
              type="button"
              disabled={disabled}
              aria-pressed={selected}
              onClick={() => {
                if (type === "single_select") return onChange({ value: option });
                onChange({ value: selected ? picked.filter((item) => item !== option) : [...picked, option] });
              }}
              className={`${CHIP} ${selected ? "border-cta bg-cta text-cta-foreground" : "border-border bg-card hover:bg-muted"}`}
            >
              {selected && type === "multi_select" && <Check className="size-3" />}
              {option}
            </button>
          );
        })}
      </div>
    );
  }
  if (type === "boolean") {
    return (
      <div role="group" aria-label="Your answer" className="mt-3 flex gap-2">
        {[
          { label: "Yes", value: true },
          { label: "No", value: false },
        ].map(({ label, value }) => (
          <button
            key={label}
            type="button"
            disabled={disabled}
            aria-pressed={draft.value === value}
            onClick={() => onChange({ value })}
            className={`${CHIP} px-4 ${draft.value === value ? "border-cta bg-cta text-cta-foreground" : "border-border bg-card hover:bg-muted"}`}
          >
            {label}
          </button>
        ))}
      </div>
    );
  }
  if (type === "number") {
    return (
      <input
        type="number"
        aria-label="Your answer"
        value={draft.message}
        disabled={disabled}
        placeholder="Enter a number…"
        onChange={(event) => onChange({ message: event.target.value })}
        className={`${FIELD} mt-3`}
      />
    );
  }
  return (
    <>
      {options.length > 0 && (
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
      <textarea
        aria-label="Your answer"
        value={draft.message}
        disabled={disabled}
        rows={2}
        placeholder="Type your answer…"
        onChange={(event) => onChange({ message: event.target.value })}
        className={`${FIELD} mt-3`}
      />
    </>
  );
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
  const details = action.name === "ask_user" ? {} : action.args;
  const hasDetails = Object.keys(details).length > 0;
  const argsError = draft.choice === "edit" && !parseArgs(draft.argsText) ? "Edited arguments must be a JSON object." : null;

  return (
    <div className="rounded-xl border border-border bg-background p-3">
      {action.name === "ask_user" ? (
        <Markdown className="font-medium">{String(action.args.question ?? action.description)}</Markdown>
      ) : (
        <p className="text-sm font-medium">{action.description}</p>
      )}
      {hasDetails && (
        <div className="mt-2 text-xs">
          <KeyValueBoxes data={details} />
        </div>
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

      {draft.choice === "respond" && <AnswerInput action={action} draft={draft} disabled={disabled} onChange={onChange} />}
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
