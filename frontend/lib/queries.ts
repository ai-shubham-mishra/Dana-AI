"use client";

import { useQuery } from "@tanstack/react-query";

import { apiGet, ApiError } from "./api";
import { useAccessToken } from "./auth";
import type { ChatSummary, JobSummary, Me } from "./types";

function useApiQuery<T>(key: string, path: string) {
  const token = useAccessToken();
  return useQuery<T, ApiError>({
    queryKey: [key, token],
    queryFn: () => apiGet<T>(path, token),
    enabled: Boolean(token),
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export const useMe = () => useApiQuery<Me>("me", "/api/v1/me");
export const useChats = () => useApiQuery<ChatSummary[]>("chats", "/api/v1/chats");
export const useJobs = () => useApiQuery<JobSummary[]>("jobs", "/api/v1/jobs");
