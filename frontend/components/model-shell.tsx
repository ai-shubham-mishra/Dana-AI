"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { formatWhen, modelHref, normalizeModelName } from "@/components/models-ui";
import { useModels } from "@/lib/queries";
import type { ModelSummary } from "@/lib/types";

export type Crumb = { label: string; href?: string };

const ALL_MODELS: Crumb = { label: "All models", href: "/models" };

export function Shell({ crumbs, children }: { crumbs: Crumb[]; children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6 p-6 md:p-10">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
        {crumbs.map((crumb, index) => (
          <span key={`${crumb.label}-${index}`} className="inline-flex items-center gap-1.5">
            {index > 0 ? <ChevronRight className="size-3.5" aria-hidden /> : null}
            {crumb.href ? (
              <Link href={crumb.href} className="hover:text-foreground">
                {crumb.label}
              </Link>
            ) : (
              <span className="font-medium text-foreground">{crumb.label}</span>
            )}
          </span>
        ))}
      </nav>
      {children}
    </div>
  );
}

function DuplicatePicker({ name, matches }: { name: string; matches: ModelSummary[] }) {
  return (
    <Shell crumbs={[ALL_MODELS, { label: name }]}>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{name}</h1>
        <p className="text-sm text-muted-foreground">Several models share this name. Choose which one to open.</p>
      </header>
      <ul className="grid gap-3 sm:grid-cols-2">
        {matches.map((model) => (
          <li key={model.id}>
            <Link
              href={modelHref(model, true)}
              className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-all duration-200 hover:border-primary/40 hover:shadow-elevated"
            >
              <span className="text-sm font-semibold">
                v{model.latest_version} · {model.version_count} version{model.version_count === 1 ? "" : "s"}
              </span>
              <span className="font-mono text-xs text-muted-foreground">{model.id}</span>
              <span className="text-xs text-muted-foreground">Created {formatWhen(model.created_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Shell>
  );
}

// Resolves a model by name (or by id for duplicate names) and renders children once it is known.
export function ModelResolver({
  name,
  modelId,
  children,
}: {
  name: string;
  modelId: string | null;
  children: (resolvedId: string, duplicate: boolean) => React.ReactNode;
}) {
  const models = useModels();
  const matches = useMemo(
    () => (models.data ?? []).filter((model) => normalizeModelName(model.name) === normalizeModelName(name)),
    [models.data, name],
  );

  if (!modelId && models.isLoading) {
    return (
      <Shell crumbs={[ALL_MODELS, { label: name }]}>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </Shell>
    );
  }

  if (!modelId && matches.length > 1) return <DuplicatePicker name={name} matches={matches} />;

  const resolvedId = modelId ?? matches[0]?.id ?? null;
  if (!resolvedId) {
    return (
      <Shell crumbs={[ALL_MODELS]}>
        <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No model named “{name}”. It may have been deleted.
        </p>
      </Shell>
    );
  }

  return <>{children(resolvedId, modelId !== null)}</>;
}
