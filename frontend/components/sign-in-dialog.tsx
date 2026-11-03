"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { KeyRound, X } from "lucide-react";
import { useState } from "react";

import { setAccessToken } from "@/lib/auth";

export function SignInDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [token, setToken] = useState("");

  function save() {
    if (!token.trim()) return;
    setAccessToken(token);
    setToken("");
    onOpenChange(false);
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,30rem)] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 text-card-foreground shadow-elevated">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold">Sign in with an access token</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                Paste a Dana AI access token issued for your organization. It is stored in this browser only.
              </Dialog.Description>
            </div>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>

          <label htmlFor="access-token" className="mt-5 block text-sm font-medium">
            Access token
          </label>
          <textarea
            id="access-token"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            rows={4}
            spellCheck={false}
            autoComplete="off"
            placeholder="eyJhbGciOiJIUzI1NiIs..."
            className="mt-2 w-full resize-none rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
          />

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close className="rounded-md px-4 py-2 text-sm text-muted-foreground hover:bg-muted">
              Cancel
            </Dialog.Close>
            <button
              type="button"
              onClick={save}
              disabled={!token.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-cta px-4 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              <KeyRound className="size-4" />
              Save token
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
