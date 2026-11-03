import { getAccessToken } from "./auth";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  status: number;
  detail: Record<string, unknown> | null;

  constructor(status: number, message: string, detail: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function raiseForStatus(res: Response): Promise<void> {
  if (res.ok) return;
  let message = res.statusText || "Request failed";
  let detail: Record<string, unknown> | null = null;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      message = body.detail;
    } else if (body.detail && typeof body.detail === "object") {
      detail = body.detail as Record<string, unknown>;
      if (typeof detail.reason === "string") message = detail.reason;
    }
  } catch {
    // Non-JSON error body; keep the status text.
  }
  throw new ApiError(res.status, message, detail);
}

export async function apiGet<T>(path: string, token: string | null = getAccessToken()): Promise<T> {
  if (!token) {
    throw new ApiError(401, "Sign in to continue");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}

export async function apiPostJson<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}

export async function apiFetchBlob(path: string, token: string): Promise<Blob> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return res.blob();
}

export async function apiDownload(path: string, token: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = match?.[1] ?? fallbackName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function apiDelete<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}

export async function apiPatchJson<T>(path: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}

export async function apiDeleteNoContent(path: string, token: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
}

export async function apiPost<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}
