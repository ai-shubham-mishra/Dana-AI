"use client";

import { motion } from "framer-motion";

import { STATUS_STYLES, isActive, progressTone } from "@/lib/job-status";
import type { JobEvent, JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const clampPercent = (percent: number) => Math.min(100, Math.max(0, percent));

export function JobProgressBar({ percent, status, className }: { percent: number; status: JobStatus; className?: string }) {
  const value = clampPercent(percent);
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}
    >
      <motion.div
        className={cn("absolute inset-y-0 left-0 overflow-hidden rounded-full transition-colors duration-500", progressTone(status, value))}
        style={isActive(status) ? { backgroundImage: "linear-gradient(90deg, var(--brand-purple), var(--primary))" } : undefined}
        initial={false}
        animate={{ width: `${value}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 24 }}
      >
        {isActive(status) ? (
          <motion.span
            aria-hidden
            className="absolute inset-y-0 w-1/3 bg-linear-to-r from-transparent via-white/50 to-transparent"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
          />
        ) : null}
      </motion.div>
    </div>
  );
}

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium capitalize", STATUS_STYLES[status])}>{status}</span>
  );
}

// Newest update first, so the latest progress sits at the top of the blade.
export function JobTimeline({ events, status, percent }: { events: JobEvent[]; status: JobStatus; percent: number }) {
  const live = isActive(status);
  const dot = progressTone(status, percent);
  const newestFirst = events.map((event, index) => ({ event, index })).reverse();

  return (
    <ol className="ml-2 space-y-3 border-l border-border pl-4">
      {newestFirst.map(({ event, index }) => {
        const isLatest = index === events.length - 1;
        return (
          <motion.li
            key={`${event.created_at}-${index}`}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className={cn("relative text-sm", !isLatest && "text-muted-foreground")}
          >
            <span className="absolute -left-[21px] top-1.5 flex size-2 items-center justify-center" aria-hidden>
              {isLatest && live ? (
                <motion.span
                  className={cn("absolute inline-flex size-2 rounded-full", dot)}
                  animate={{ scale: [1, 2.2, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                />
              ) : null}
              <span
                className={cn("relative inline-flex size-2 rounded-full transition-colors duration-500", isLatest ? dot : "bg-muted-foreground/40")}
              />
            </span>
            <span className="text-xs tabular-nums text-muted-foreground">{event.percent}%</span>{" "}
            <span className={cn(isLatest && "font-medium")}>{event.message}</span>
          </motion.li>
        );
      })}
    </ol>
  );
}
