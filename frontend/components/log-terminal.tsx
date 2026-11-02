"use client";

import { ArrowDown, Check, Copy, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { LogStreamState } from "@/lib/deployment-logs";
import { cn } from "@/lib/utils";

const STATE_LABEL: Record<LogStreamState, string> = {
  idle: "Idle",
  connecting: "Connecting",
  streaming: "Live",
  ended: "Ended",
  error: "Error",
};

const STATE_STYLE: Record<LogStreamState, string> = {
  idle: "bg-white/10 text-white/60",
  connecting: "bg-amber-400/15 text-amber-300",
  streaming: "bg-teal/20 text-teal",
  ended: "bg-white/10 text-white/70",
  error: "bg-red-500/20 text-red-300",
};

const FOLLOW_THRESHOLD_PX = 24;

function lineTone(line: string): string {
  if (/error|traceback|exception|critical/i.test(line)) return "text-red-300";
  if (/warn/i.test(line)) return "text-amber-300";
  if (/running on|started|ready|application startup complete/i.test(line)) return "text-teal";
  return "text-white/80";
}

export function LogTerminal({
  title,
  lines,
  state,
  error,
}: {
  title: string;
  lines: string[];
  state: LogStreamState;
  error: string | null;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const body = bodyRef.current;
    if (follow && body) body.scrollTop = body.scrollHeight;
  }, [lines, follow]);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  function onScroll() {
    const body = bodyRef.current;
    if (!body) return;
    const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < FOLLOW_THRESHOLD_PX;
    setFollow(atBottom);
  }

  function jumpToLatest() {
    setFollow(true);
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }

  async function copyLogs() {
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/10 bg-[#0b0618] text-white shadow-elevated">
      <div className="flex items-center gap-3 border-b border-white/10 px-4 py-2.5">
        <div className="flex gap-1.5" aria-hidden>
          <span className="size-2.5 rounded-full bg-red-400/80" />
          <span className="size-2.5 rounded-full bg-amber-300/80" />
          <span className="size-2.5 rounded-full bg-teal/80" />
        </div>
        <span className="flex min-w-0 items-center gap-2 text-xs text-white/70">
          <Terminal className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate font-mono">{title}</span>
        </span>
        <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", STATE_STYLE[state])}>{STATE_LABEL[state]}</span>
        <span className="ml-auto text-[11px] tabular-nums text-white/50">{lines.length} lines</span>
        <button
          type="button"
          onClick={copyLogs}
          disabled={lines.length === 0}
          aria-label="Copy logs"
          className="rounded-md p-1.5 text-white/60 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-40"
        >
          {copied ? <Check className="size-3.5 text-teal" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        </button>
      </div>

      <div className="relative">
        <div
          ref={bodyRef}
          onScroll={onScroll}
          role="log"
          aria-live="off"
          className="h-72 overflow-auto px-4 py-3 font-mono text-xs leading-5"
        >
          {error ? <p className="text-red-300">{error}</p> : null}
          {!error && lines.length === 0 ? (
            <p className="text-white/40">{state === "ended" ? "No output was recorded." : "Waiting for output…"}</p>
          ) : null}
          {lines.map((line, index) => (
            <div key={index} className="flex gap-3 whitespace-pre-wrap break-all">
              <span className="w-10 shrink-0 select-none text-right tabular-nums text-white/25">{index + 1}</span>
              <span className={lineTone(line)}>{line}</span>
            </div>
          ))}
        </div>
        {!follow ? (
          <button
            type="button"
            onClick={jumpToLatest}
            className="absolute bottom-3 right-4 inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1.5 text-xs font-medium text-white shadow-elevated transition-transform hover:scale-[1.03]"
          >
            <ArrowDown className="size-3.5" aria-hidden />
            Jump to latest
          </button>
        ) : null}
      </div>
    </div>
  );
}
