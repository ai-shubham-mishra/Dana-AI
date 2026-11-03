export const PREVIEW_MAX_BYTES = 2 * 1024 * 1024;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const PREVIEWABLE_EXTENSIONS = new Set([
  "csv",
  "tsv",
  "txt",
  "md",
  "json",
  "yml",
  "yaml",
  "toml",
  "ini",
  "cfg",
  "py",
  "sql",
  "log",
  "xml",
  "html",
  "js",
  "ts",
  "sh",
]);

export function isPreviewableArtifact(name: string, bytes: number): boolean {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return PREVIEWABLE_EXTENSIONS.has(name.slice(dot + 1).toLowerCase()) && bytes <= PREVIEW_MAX_BYTES;
}

export function formatPreviewText(name: string, text: string): string {
  if (!name.toLowerCase().endsWith(".json")) return text;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}
