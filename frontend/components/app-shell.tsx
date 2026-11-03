"use client";

import { useState, type ReactNode } from "react";

import { Sidebar } from "@/components/sidebar";
import { SignInDialog } from "@/components/sign-in-dialog";

export function AppShell({ children }: { children: ReactNode }) {
  const [signInOpen, setSignInOpen] = useState(false);
  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <Sidebar onSignIn={() => setSignInOpen(true)} />
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">{children}</main>
      <SignInDialog open={signInOpen} onOpenChange={setSignInOpen} />
    </div>
  );
}
