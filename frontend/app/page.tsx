"use client";

import { BarChart3, Cable, Sparkles } from "lucide-react";

import { Wordmark } from "@/components/wordmark";
import { useAccessToken } from "@/lib/auth";

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

export default function HomePage() {
  const token = useAccessToken();

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4 md:px-10">
        <Wordmark compact />
        <span className="rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
          Milestone 1 · Shell
        </span>
      </header>

      <section className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 py-16 text-center">
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
          What should we <span className="text-primary">train</span> today?
        </h1>
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
  );
}
