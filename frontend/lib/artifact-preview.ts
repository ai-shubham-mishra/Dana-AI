import readXlsxFile from "read-excel-file/browser";

export const PREVIEW_MAX_BYTES = 2 * 1024 * 1024;
export const PREVIEW_MAX_ROWS = 1000;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export type CodeLanguage = "python" | "yaml" | "json" | "sql" | "javascript" | "typescript" | "markup";

const CODE_LANGUAGES: Record<string, CodeLanguage> = {
  py: "python",
  yml: "yaml",
  yaml: "yaml",
  json: "json",
  sql: "sql",
  js: "javascript",
  ts: "typescript",
  xml: "markup",
  html: "markup",
};

const TEXT_EXTENSIONS = new Set(["txt", "md", "toml", "ini", "cfg", "log", "sh"]);
const TABLE_EXTENSIONS = new Set(["csv", "tsv"]);
const SHEET_EXTENSIONS = new Set(["xlsx"]);

export type TablePreview = {
  headers: string[];
  rows: string[][];
  totalRows: number;
  width: number;
};

export type ArtifactPreview =
  | { kind: "code"; language: CodeLanguage; text: string }
  | { kind: "text"; text: string }
  | { kind: "table"; table: TablePreview }
  | { kind: "sheets"; sheets: { name: string; table: TablePreview }[] };

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isPreviewableArtifact(name: string, bytes: number): boolean {
  const ext = extensionOf(name);
  const supported =
    ext in CODE_LANGUAGES || TEXT_EXTENSIONS.has(ext) || TABLE_EXTENSIONS.has(ext) || SHEET_EXTENSIONS.has(ext);
  return supported && bytes <= PREVIEW_MAX_BYTES;
}

export function parseDelimited(text: string, delimiter: string): string[][] {
  const src = text.replace(/^\uFEFF/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        quoted = false;
      } else {
        field += ch;
      }
      i++;
      continue;
    }
    if (ch === '"' && field === "") {
      quoted = true;
    } else if (ch === delimiter) {
      row.push(field);
      field = "";
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && src[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
    i++;
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.some((cell) => cell.trim() !== ""));
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? "" : value.toISOString().slice(0, 19).replace("T", " ");
  return String(value);
}

export function buildTable(rows: string[][]): TablePreview {
  const kept = rows.filter((r) => r.some((cell) => cell.trim() !== ""));
  const width = kept.reduce((max, r) => Math.max(max, r.length), 0);
  const pad = (r: string[]) => Array.from({ length: width }, (_, i) => r[i] ?? "");
  const [header = [], ...body] = kept;
  return {
    headers: pad(header),
    rows: body.slice(0, PREVIEW_MAX_ROWS).map(pad),
    totalRows: body.length,
    width,
  };
}

export async function parseArtifactPreview(name: string, blob: Blob): Promise<ArtifactPreview> {
  const ext = extensionOf(name);
  if (SHEET_EXTENSIONS.has(ext)) {
    const sheets = await readXlsxFile(blob);
    return {
      kind: "sheets",
      sheets: sheets.map((s) => ({
        name: s.sheet,
        table: buildTable(s.data.map((row) => row.map(formatCell))),
      })),
    };
  }
  const text = await blob.text();
  if (TABLE_EXTENSIONS.has(ext)) {
    return { kind: "table", table: buildTable(parseDelimited(text, ext === "tsv" ? "\t" : ",")) };
  }
  const language = CODE_LANGUAGES[ext];
  if (language) {
    return { kind: "code", language, text: formatPreviewText(name, text) };
  }
  return { kind: "text", text };
}

export function formatPreviewText(name: string, text: string): string {
  if (!name.toLowerCase().endsWith(".json")) return text;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}
