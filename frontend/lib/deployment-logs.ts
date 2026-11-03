"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL, raiseForStatus } from "./api";
import { useAccessToken } from "./auth";
import { readSse } from "./sse";

export type LogStreamState = "idle" | "connecting" | "streaming" | "ended" | "error";

type LogStream = { key: string; lines: string[]; state: LogStreamState; error: string | null };

const MAX_LINES = 2000;

// fetch rather than EventSource, because EventSource cannot send the Authorization header.
export function useDeploymentLogs(depId: string | null) {
  const token = useAccessToken();
  const [stream, setStream] = useState<LogStream | null>(null);

  useEffect(() => {
    if (!token || !depId) return;

    const controller = new AbortController();
    const patch = (update: Partial<Omit<LogStream, "key">>, appendLine?: string) =>
      setStream((prev) => {
        const base = prev?.key === depId ? prev : { key: depId, lines: [], state: "connecting" as const, error: null };
        const lines = appendLine === undefined ? base.lines : [...base.lines, appendLine].slice(-MAX_LINES);
        return { ...base, ...update, lines };
      });

    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/deployments/${encodeURIComponent(depId)}/logs`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
          signal: controller.signal,
        });
        await raiseForStatus(res);
        if (!res.body) throw new Error("The log stream is empty");
        patch({ state: "streaming" });
        for await (const frame of readSse(res.body)) {
          if (frame.event === "end") break;
          patch({}, JSON.parse(frame.data) as string);
        }
        if (!controller.signal.aborted) patch({ state: "ended" });
      } catch (err) {
        if (controller.signal.aborted) return;
        patch({ state: "error", error: err instanceof Error ? err.message : "Log stream failed" });
      }
    })();

    return () => controller.abort();
  }, [token, depId]);

  if (!depId || !token) return { lines: [] as string[], state: "idle" as LogStreamState, error: null as string | null };
  if (!stream || stream.key !== depId) return { lines: [] as string[], state: "connecting" as LogStreamState, error: null as string | null };
  return { lines: stream.lines, state: stream.state, error: stream.error };
}
