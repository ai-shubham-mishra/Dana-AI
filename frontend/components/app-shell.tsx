"use client";

import { useState, type ReactNode } from "react";

import { Sidebar } from "@/components/sidebar";
import { SignInDialog } from "@/components/sign-in-dialog";

export function AppShell({ children }: { children: ReactNode }) {
  const [signInOpen, setSignInOpen] = useState(false);
  return (
    <div className="flex min-h-dvh bg-background">
      <Sidebar onSignIn={() => setSignInOpen(true)} />
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
      <SignInDialog open={signInOpen} onOpenChange={setSignInOpen} />
    </div>
  );
}
