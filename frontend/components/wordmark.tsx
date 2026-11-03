import { cn } from "@/lib/utils";

export function Wordmark({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-baseline font-semibold tracking-tight select-none",
        compact ? "text-base" : "text-2xl",
        className,
      )}
    >
      <span>Dana</span>
      <span className="ml-1 text-primary">AI</span>
    </span>
  );
}
