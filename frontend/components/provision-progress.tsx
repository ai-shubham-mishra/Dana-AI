"use client";

import { motion } from "framer-motion";

export function ProvisionProgress({ percent, stage }: { percent: number; stage: string | null }) {
  const value = Math.max(0, Math.min(100, Math.round(percent)));
  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="truncate text-muted-foreground">{stage ?? "Starting"}</span>
        <span className="font-mono tabular-nums text-primary">{value}%</span>
      </div>
      <div
        role="progressbar"
        aria-label="Container allocation progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        className="relative h-2 overflow-hidden rounded-full bg-primary/15"
      >
        <motion.div
          className="absolute inset-y-0 left-0 overflow-hidden rounded-full bg-linear-to-r from-primary to-cta"
          initial={false}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          <motion.div
            className="absolute inset-y-0 w-1/3 bg-linear-to-r from-transparent via-white/50 to-transparent"
            animate={{ x: ["-100%", "300%"] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
          />
        </motion.div>
      </div>
    </div>
  );
}
