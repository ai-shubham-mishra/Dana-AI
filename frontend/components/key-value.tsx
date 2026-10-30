import { cn } from "@/lib/utils";

type Nested = Record<string, unknown> | unknown[];

function isNested(value: unknown): value is Nested {
  return value !== null && typeof value === "object";
}

function entriesOf(value: Nested): [string, unknown][] {
  return Array.isArray(value) ? value.map((item, index) => [String(index), item]) : Object.entries(value);
}

function Leaf({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">—</span>;
  if (typeof value === "number") return <span>{Number.isInteger(value) ? String(value) : value.toFixed(4)}</span>;
  if (typeof value === "boolean") return <span>{value ? "true" : "false"}</span>;
  return <span className="whitespace-pre-wrap break-all">{String(value)}</span>;
}

function Value({ value }: { value: unknown }) {
  if (!isNested(value)) return <Leaf value={value} />;
  if (entriesOf(value).length === 0) return <Leaf value={null} />;
  if (Array.isArray(value) && value.every((item) => !isNested(item))) {
    return <Leaf value={value.map(String).join(", ")} />;
  }
  return (
    <div className="rounded-md border border-border bg-muted/40 p-2">
      <KeyValueBoxes data={value} />
    </div>
  );
}

export function KeyValueBoxes({ data, className }: { data: unknown; className?: string }) {
  if (!isNested(data)) return <Leaf value={data} />;
  const entries = entriesOf(data);
  if (entries.length === 0) return <Leaf value={null} />;
  return (
    <dl className={cn("grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm", className)}>
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="pt-0.5 text-muted-foreground">{key}</dt>
          <dd className="min-w-0">
            <Value value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
