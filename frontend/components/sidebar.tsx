"use client";

import { motion } from "framer-motion";
import { LayoutDashboard, LogIn, LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";
import { clearAccessToken, useAccessToken } from "@/lib/auth";
import { useMe } from "@/lib/queries";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/jobs", label: "Jobs", icon: LayoutDashboard },
];

export function Sidebar({ onSignIn }: { onSignIn: () => void }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
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

      <nav aria-label="Primary" className="flex flex-col gap-1 px-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              title={label}
              className={cn(
                "relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                collapsed && "justify-center px-0",
                active
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {active && <span aria-hidden className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />}
              <Icon className="size-4 shrink-0" />
              {!collapsed && label}
            </Link>
          );
        })}
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
