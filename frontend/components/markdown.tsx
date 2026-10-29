"use client";

import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

const components: Components = {
  p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
  h1: (props) => <h3 className="mb-2 mt-4 text-base font-semibold first:mt-0" {...props} />,
  h2: (props) => <h3 className="mb-2 mt-4 text-base font-semibold first:mt-0" {...props} />,
  h3: (props) => <h4 className="mb-1.5 mt-3 text-sm font-semibold first:mt-0" {...props} />,
  h4: (props) => <h4 className="mb-1.5 mt-3 text-sm font-semibold first:mt-0" {...props} />,
  ul: (props) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-primary" {...props} />,
  ol: (props) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-muted-foreground" {...props} />,
  li: (props) => <li className="pl-1" {...props} />,
  strong: (props) => <strong className="font-semibold text-foreground" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  a: ({ className, ...props }: ComponentPropsWithoutRef<"a">) => (
    <a
      className={cn("font-medium text-primary underline underline-offset-2 hover:opacity-80", className)}
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    />
  ),
  blockquote: (props) => <blockquote className="my-3 border-l-2 border-primary pl-3 text-muted-foreground" {...props} />,
  hr: () => <hr className="my-4 border-border" />,
  code: ({ className, children, ...props }: ComponentPropsWithoutRef<"code">) => {
    const isBlock = Boolean(className?.startsWith("language-"));
    if (isBlock) {
      return (
        <code className={cn("block font-mono text-xs leading-5", className)} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]" {...props}>
        {children}
      </code>
    );
  },
  pre: (props) => (
    <pre className="my-3 overflow-x-auto rounded-lg border border-border bg-muted p-3 text-foreground" {...props} />
  ),
  table: (props) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-left text-sm" {...props} />
    </div>
  ),
  thead: (props) => <thead className="bg-muted text-xs uppercase tracking-wide text-muted-foreground" {...props} />,
  th: (props) => <th className="border-b border-border px-3 py-2 font-semibold" {...props} />,
  td: (props) => <td className="border-b border-border px-3 py-2 align-top" {...props} />,
};

export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("min-w-0 break-words text-sm leading-6", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
