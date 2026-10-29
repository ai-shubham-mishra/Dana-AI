"use client";

import { motion } from "framer-motion";
import {
  ChevronDown,
  ChevronRight,
  LayoutDashboard,
  LogIn,
  LogOut,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";
import { clearAccessToken, useAccessToken } from "@/lib/auth";
import { useChatSelection } from "@/lib/chat-selection";
import { relativeTime } from "@/lib/format";
import { useChats, useMe } from "@/lib/queries";
import type { ChatSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHAT_PATH = "/chat";

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
  className,
}: {
  href: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  collapsed: boolean;
  className?: string;
}) {
  return (
    <Link
      href={href}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      title={label}
      className={cn(
        "relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
        collapsed && "justify-center px-0",
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
        className,
      )}
    >
      {active && <span aria-hidden className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />}
      <Icon className="size-4 shrink-0" />
      {!collapsed && label}
    </Link>
  );
}

function SessionList({
  signedIn,
  items,
  isPending,
  error,
  activeChatId,
  disabled,
  onSelect,
}: {
  signedIn: boolean;
  items: ChatSummary[];
  isPending: boolean;
  error: Error | null;
  activeChatId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  if (!signedIn) return <p className="px-3 py-2 text-xs text-muted-foreground">Sign in to see your chats</p>;
  if (isPending) return <p className="px-3 py-2 text-xs text-muted-foreground">Loading…</p>;
  if (error) return <p className="px-3 py-2 text-xs text-destructive">{error.message}</p>;
  if (items.length === 0) return <p className="px-3 py-2 text-xs text-muted-foreground">No chats yet</p>;

  return (
    <ul className="space-y-0.5">
      {items.map((chat) => {
        const active = chat.id === activeChatId;
        return (
          <li key={chat.id}>
            <button
              type="button"
              title={chat.title}
              aria-current={active ? "true" : undefined}
              disabled={disabled}
              onClick={() => onSelect(chat.id)}
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md py-1.5 pl-9 pr-3 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                active ? "bg-magenta-wash text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <span className="truncate">{chat.title}</span>
              <span className="shrink-0 text-[11px] text-muted-foreground">{relativeTime(chat.updated_at)}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function Sidebar({ onSignIn }: { onSignIn: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const [chatsOpen, setChatsOpen] = useState(true);
  const pathname = usePathname();
  const router = useRouter();
  const token = useAccessToken();
  const me = useMe();
  const chats = useChats();
  const activeChatId = useChatSelection((state) => state.activeChatId);
  const busy = useChatSelection((state) => state.busy);
  const selectChat = useChatSelection((state) => state.select);
  const onChatPage = pathname === CHAT_PATH;

  function openChat(chatId: string | null) {
    selectChat(chatId);
    if (!onChatPage) router.push(CHAT_PATH);
  }

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

      <div className="px-3 pb-2">
        <button
          type="button"
          disabled={!token || busy}
          aria-label="New chat"
          title="New chat"
          onClick={() => openChat(null)}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-md bg-cta px-3 py-2.5 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50",
            !collapsed && "justify-start",
          )}
        >
          <Plus className="size-4 shrink-0" />
          {!collapsed && "New chat"}
        </button>
      </div>

      <nav aria-label="Primary" className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-3">
        <NavLink href="/jobs" label="Jobs" icon={LayoutDashboard} active={pathname.startsWith("/jobs")} collapsed={collapsed} />

        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <NavLink
              href={CHAT_PATH}
              label="Chat"
              icon={MessageSquare}
              active={onChatPage}
              collapsed={collapsed}
              className="min-w-0 flex-1"
            />
            {!collapsed && (
              <button
                type="button"
                onClick={() => setChatsOpen((value) => !value)}
                aria-label={chatsOpen ? "Hide chats" : "Show chats"}
                aria-expanded={chatsOpen}
                className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {chatsOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
              </button>
            )}
          </div>
          {!collapsed && chatsOpen && (
            <SessionList
              signedIn={Boolean(token)}
              items={chats.data ?? []}
              isPending={chats.isPending}
              error={chats.error}
              activeChatId={activeChatId}
              disabled={busy}
              onSelect={(id) => openChat(id)}
            />
          )}
        </div>
      </nav>

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
        {(!token || me.error) && (
          <button
            type="button"
            onClick={onSignIn}
            aria-label="Sign in"
            title="Sign in with an access token"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <LogIn className="size-4" />
          </button>
        )}
        {token && (
          <button
            type="button"
            onClick={clearAccessToken}
            aria-label="Sign out"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <LogOut className="size-4" />
          </button>
        )}
      </div>
    </motion.aside>
  );
}
