import { cn } from "@/lib/utils";

type Nested = Record<string, unknown> | unknown[];

function isNested(value: unknown): value is Nested {
  return value !== null && typeof value === "object";
}

function entriesOf(value: Nested): [string, unknown][] {
  return Array.isArray(value) ? value.map((item, index) => [`#${index + 1}`, item]) : Object.entries(value);
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
  return <NestedBlocks data={value} />;
}

function NestedBlocks({ data }: { data: Nested }) {
  return (
    <div className="space-y-2">
      {entriesOf(data).map(([key, value]) => (
        <div key={key} className="min-w-0 rounded-md border border-border bg-muted/30 px-3 py-2">
          <div className="break-words text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{key}</div>
          <div className="mt-1 min-w-0 text-sm">
            <Value value={value} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function KeyValueBoxes({ data, className }: { data: unknown; className?: string }) {
  if (!isNested(data)) return <Leaf value={data} />;
  const entries = entriesOf(data);
  if (entries.length === 0) return <Leaf value={null} />;
  return (
    <dl className={cn("grid grid-cols-[minmax(0,8rem)_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm", className)}>
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="min-w-0 break-words pt-0.5 text-muted-foreground">{key}</dt>
          <dd className="min-w-0">
            <Value value={value} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
