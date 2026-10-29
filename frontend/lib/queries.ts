"use client";

import { useQuery } from "@tanstack/react-query";

import { apiGet, ApiError } from "./api";
import { useAccessToken } from "./auth";
import type { ChatSummary, JobSummary, Me } from "./types";

const POLL_INTERVAL_MS = 5000;

function useApiQuery<T>(key: string, path: string, pollWhile?: (data: T) => boolean) {
  const token = useAccessToken();
  return useQuery<T, ApiError>({
    queryKey: [key, token],
    queryFn: () => apiGet<T>(path, token),
    enabled: Boolean(token),
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
    refetchInterval: (query) => (pollWhile && query.state.data && pollWhile(query.state.data) ? POLL_INTERVAL_MS : false),
  });
}

const hasActiveJob = (jobs: JobSummary[]) => jobs.some((job) => job.status === "queued" || job.status === "running");

export const useMe = () => useApiQuery<Me>("me", "/api/v1/me");
export const useChats = () => useApiQuery<ChatSummary[]>("chats", "/api/v1/chats");
export const useJobs = () => useApiQuery<JobSummary[]>("jobs", "/api/v1/jobs", hasActiveJob);
