"use client";

import { BarChart3, Cable, Plus, Sparkles } from "lucide-react";

import { useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useChats } from "@/lib/queries";

const CAPABILITIES = [
  {
    icon: Cable,
    title: "Connect your data",
    body: "Link Meta Ads, Google Ads and other connectors. Dana reads each connector table in your organization's schema.",
  },
  {
    icon: Sparkles,
    title: "Shape the model",
    body: "Describe the outcome you want. Dana asks about channels, date ranges and constraints, then drafts the training code.",
  },
  {
    icon: BarChart3,
    title: "Train and track",
    body: "Run MMM training locally or on Azure ML, with live progress, approvals and results saved per job.",
  },
];

function ChatHistory() {
  const token = useAccessToken();
  const chats = useChats();
  const items = chats.data ?? [];

  if (!token) return <p className="px-3 py-2 text-sm text-muted-foreground">Sign in to see your chats</p>;
  if (chats.isPending) return <p className="px-3 py-2 text-sm text-muted-foreground">Loading…</p>;
  if (chats.error) return <p className="px-3 py-2 text-sm text-destructive">{chats.error.message}</p>;
  if (items.length === 0) return <p className="px-3 py-2 text-sm text-muted-foreground">No chats yet</p>;

  return (
    <div className="space-y-1">
      {items.map((chat) => (
        <button
          key={chat.id}
          type="button"
          className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-muted"
        >
          <span className="truncate">{chat.title}</span>
          <span className="shrink-0 text-[11px] text-muted-foreground">{relativeTime(chat.updated_at)}</span>
        </button>
      ))}
    </div>
  );
}

export function ChatWindow() {
  const token = useAccessToken();

  return (
    <div className="flex h-dvh min-h-0 min-w-0 flex-1">
      <section aria-label="Chat history" className="hidden w-64 shrink-0 flex-col border-r border-border lg:flex">
        <div className="p-3">
          <button
            type="button"
            disabled={!token}
            aria-label="New chat"
            className="flex w-full items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="size-4" />
            New chat
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          <ChatHistory />
        </div>
      </section>

      <div className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <header className="flex items-center justify-between border-b border-border px-6 py-4 md:px-10">
          <h1 className="text-sm font-semibold">Chat</h1>
          <span className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
            Milestone 1 · Shell
          </span>
        </header>

        <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
          <h2 className="text-4xl font-semibold tracking-tight md:text-5xl">
            What should we <span className="text-primary">train</span> today?
          </h2>
          <p className="mt-4 max-w-xl text-base text-muted-foreground">
            Dana AI turns your marketing data into predictive models. It asks the right questions, writes the training
            code for your data, and keeps you updated while jobs run.
          </p>

          {!token && (
            <p className="mt-6 rounded-md border border-border bg-card px-4 py-2 text-sm text-muted-foreground">
              Sign in with an access token from the sidebar to load your chats and jobs.
            </p>
          )}

          <div className="mt-10 grid w-full gap-4 md:grid-cols-3">
            {CAPABILITIES.map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-shadow hover:shadow-elevated"
              >
                <div className="mb-3 inline-flex size-9 items-center justify-center rounded-lg bg-magenta-wash text-primary">
                  <Icon className="size-4" />
                </div>
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
              </div>
            ))}
          </div>

          <div className="mt-10 w-full rounded-2xl border border-border bg-card p-3 text-left shadow-elevated">
            <textarea
              disabled
              rows={2}
              placeholder="Chat arrives in the next milestone…"
              className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            />
            <div className="flex justify-end">
              <button
                type="button"
                disabled
                className="rounded-md bg-cta px-4 py-1.5 text-sm font-medium text-cta-foreground opacity-50"
              >
                Send
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
