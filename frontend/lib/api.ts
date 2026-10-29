import { getAccessToken } from "./auth";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function raiseForStatus(res: Response): Promise<void> {
  if (res.ok) return;
  let message = res.statusText || "Request failed";
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    // Non-JSON error body; keep the status text.
  }
  throw new ApiError(res.status, message);
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

export async function apiPost<T>(path: string, token: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  await raiseForStatus(res);
  return (await res.json()) as T;
}
