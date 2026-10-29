"use client";

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";

import { Markdown } from "@/components/markdown";

// Mirrors backend split_reply: text before the last tool event is process, the rest is the answer.
export function splitReply(text: string, boundary: number) {
  return { process: text.slice(0, boundary).trimEnd(), answer: text.slice(boundary).trimStart() };
}

export function ReasoningTicker({ text }: { text: string }) {
  return (
    <div className="flex h-[3rem] flex-col justify-end overflow-hidden text-xs leading-6 text-muted-foreground">
      <Markdown animateWords className="text-xs leading-6">
        {text}
      </Markdown>
    </div>
  );
}

const DOT_PATTERNS: Array<(row: number, col: number) => number> = [
  (row, col) => row + col,
  (row, col) => row + (3 - col),
  (row) => row,
  (_, col) => col,
];

export function MatrixDotLoader() {
  const [pattern, setPattern] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setPattern((current) => (current + 1) % DOT_PATTERNS.length), 1600);
    return () => window.clearInterval(id);
  }, []);

  const rule = DOT_PATTERNS[pattern];
  return (
    <div className="grid h-[11px] w-[11px] shrink-0 grid-cols-4 gap-px" aria-hidden="true">
      {Array.from({ length: 16 }, (_, index) => {
        const delay = (rule(Math.floor(index / 4), index % 4) % 4) * 0.12;
        return (
          <span
            key={`${pattern}-${index}`}
            className="dana-dot size-0.5 rounded-full bg-primary"
            style={{ "--dot-delay": `${delay}s` } as CSSProperties}
          />
        );
      })}
    </div>
  );
}

export function StatusLine({ label }: { label: string }) {
  return (
    <span className="relative inline-flex h-5 items-center overflow-hidden text-xs font-medium">
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={label}
          initial={{ opacity: 0, filter: "blur(4px)", y: 6 }}
          animate={{ opacity: 1, filter: "blur(0px)", y: 0 }}
          exit={{ opacity: 0, filter: "blur(4px)", y: -6 }}
          transition={{ duration: 0.25 }}
          className="dana-shimmer whitespace-nowrap"
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export function ToolStatusIcon({ done }: { done: boolean }) {
  return (
    <span className="relative flex size-3.5 shrink-0 items-center justify-center">
      <AnimatePresence initial={false} mode="wait">
        {done ? (
          <motion.svg
            key="check"
            viewBox="0 0 16 16"
            className="size-3.5 text-primary"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 22 }}
            aria-label="Done"
          >
            <motion.path
              d="M3.5 8.5 6.5 11.5 12.5 4.5"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.3, ease: "easeOut" }}
            />
          </motion.svg>
        ) : (
          <motion.span
            key="spinner"
            className="flex"
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.4, opacity: 0 }}
            transition={{ duration: 0.2 }}
            aria-label="Running"
          >
            <svg viewBox="0 0 16 16" className="size-3.5 animate-spin text-muted-foreground" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
              <circle cx="8" cy="8" r="6" strokeDasharray="28 10" />
            </svg>
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}

export function ThinkingBlock({
  live,
  status,
  hasContent,
  defaultOpen = false,
  children,
}: {
  live: boolean;
  status?: string;
  hasContent: boolean;
  defaultOpen?: boolean;
  children?: ReactNode;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = userOpen ?? defaultOpen;

  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setUserOpen(!open)}
        aria-expanded={open}
        className="flex items-center gap-2 py-1 text-left"
      >
        {live && <MatrixDotLoader />}
        {live ? (
          <StatusLine label={status ?? "Thinking…"} />
        ) : (
          <span className="text-xs font-medium text-muted-foreground">Thinking</span>
        )}
        <ChevronDown
          className={`size-3.5 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && hasContent && <div className="mt-2 space-y-3">{children}</div>}
    </div>
  );
}

