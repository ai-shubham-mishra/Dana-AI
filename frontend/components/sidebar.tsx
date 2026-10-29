"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { motion } from "framer-motion";
import { Briefcase, LogIn, LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";
import { clearAccessToken, useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useChats, useJobs, useMe } from "@/lib/queries";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-accent text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-destructive/15 text-destructive",
  cancelled: "bg-muted text-muted-foreground",
};

function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] font-medium capitalize",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}

function ListState({ loading, error, empty, emptyText }: { loading: boolean; error: Error | null; empty: boolean; emptyText: string }) {
  if (loading) return <p className="px-3 py-2 text-sm text-muted-foreground">Loading…</p>;
  if (error) return <p className="px-3 py-2 text-sm text-destructive">{error.message}</p>;
  if (empty) return <p className="px-3 py-2 text-sm text-muted-foreground">{emptyText}</p>;
  return null;
}

function ChatsList() {
  const token = useAccessToken();
  const chats = useChats();
  const items = chats.data ?? [];
  return (
    <div className="space-y-1">
      <ListState
        loading={Boolean(token) && chats.isPending}
        error={chats.error}
        empty={!chats.isPending && !chats.error && items.length === 0}
        emptyText={token ? "No chats yet" : "Sign in to see your chats"}
      />
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

function JobsList() {
  const token = useAccessToken();
  const jobs = useJobs();
  const items = jobs.data ?? [];
  return (
    <div className="space-y-1">
      <ListState
        loading={Boolean(token) && jobs.isPending}
        error={jobs.error}
        empty={!jobs.isPending && !jobs.error && items.length === 0}
        emptyText={token ? "No training jobs yet" : "Sign in to see your jobs"}
      />
      {items.map((job) => (
        <div key={job.id} className="rounded-md px-3 py-2 hover:bg-muted">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium">{job.title}</span>
            <StatusBadge status={job.status} />
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {job.kind} · {relativeTime(job.created_at)}
          </div>
        </div>
      ))}
    </div>
  );
}

export function Sidebar({ onSignIn }: { onSignIn: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const token = useAccessToken();
  const me = useMe();

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 272 }}
      transition={{ type: "spring", stiffness: 380, damping: 36 }}
      className="sticky top-0 flex h-dvh shrink-0 flex-col overflow-hidden border-r border-sidebar-border bg-sidebar"
    >
      <div className="flex items-center justify-between gap-2 px-3 py-4">
        {!collapsed && <Wordmark compact />}
        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </div>

      <div className="px-3">
        <button
          type="button"
          disabled={!token}
          aria-label="New chat"
          className={cn(
            "flex w-full items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50",
            collapsed && "justify-center px-0",
          )}
        >
          <Plus className="size-4" />
          {!collapsed && "New chat"}
        </button>
      </div>

      {collapsed ? (
        <div className="mt-4 flex flex-col items-center gap-2 text-muted-foreground">
          <MessageSquare className="size-4" aria-hidden />
          <Briefcase className="size-4" aria-hidden />
        </div>
      ) : (
        <Tabs.Root defaultValue="chats" className="mt-4 flex min-h-0 flex-1 flex-col">
          <Tabs.List className="mx-3 grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
            <Tabs.Trigger
              value="chats"
              className="flex items-center justify-center gap-2 rounded-sm px-2 py-1.5 text-sm text-muted-foreground transition-colors data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm"
            >
              <MessageSquare className="size-4" />
              Chats
            </Tabs.Trigger>
            <Tabs.Trigger
              value="jobs"
              className="flex items-center justify-center gap-2 rounded-sm px-2 py-1.5 text-sm text-muted-foreground transition-colors data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm"
            >
              <Briefcase className="size-4" />
              Jobs
            </Tabs.Trigger>
          </Tabs.List>
          <div className="min-h-0 flex-1 overflow-y-auto px-2 py-3">
            <Tabs.Content value="chats" className="outline-none">
              <ChatsList />
            </Tabs.Content>
            <Tabs.Content value="jobs" className="outline-none">
              <JobsList />
            </Tabs.Content>
          </div>
        </Tabs.Root>
      )}

      <div className="mt-auto flex items-center gap-2 border-t border-sidebar-border p-3">
        {!collapsed && (
          <div className="min-w-0 flex-1">
            {token && me.data ? (
              <>
                <div className="truncate text-sm font-medium">{me.data.email ?? me.data.user_id}</div>
                <div className="truncate text-[11px] capitalize text-muted-foreground">
                  {me.data.role} · {me.data.org_id}
                </div>
              </>
            ) : token && me.error ? (
              <div className="text-sm text-destructive">Token rejected. Sign in again.</div>
            ) : (
              <div className="text-sm text-muted-foreground">{token ? "Loading…" : "Not signed in"}</div>
            )}
          </div>
        )}
        <ThemeToggle className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" />
        {token ? (
          <button
            type="button"
            onClick={clearAccessToken}
            aria-label="Sign out"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={onSignIn}
            aria-label="Sign in"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <LogIn className="size-4" />
          </button>
        )}
      </div>
    </motion.aside>
  );
}
