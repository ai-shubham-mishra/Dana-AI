"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiGet, apiPostJson, ApiError } from "./api";
import { useAccessToken } from "./auth";
import type { ChatMessage, ChatSummary, ConnectorPage, ConnectorSummary, DeleteJobsResult, JobDetail, JobSummary, Me, PendingApproval } from "./types";

const POLL_INTERVAL_MS = 5000;
const CHATS_REFRESH_MS = 10_000;

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
export function useChats() {
  const token = useAccessToken();
  return useQuery<ChatSummary[], ApiError>({
    queryKey: ["chats", token],
    queryFn: () => apiGet<ChatSummary[]>("/api/v1/chats", token),
    enabled: Boolean(token),
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
    refetchInterval: CHATS_REFRESH_MS,
    refetchOnWindowFocus: true,
  });
}
export const useJobs = () => useApiQuery<JobSummary[]>("jobs", "/api/v1/jobs", hasActiveJob);

export function useDeleteJobs() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return useMutation<DeleteJobsResult, ApiError, string[]>({
    mutationFn: (jobIds) => apiPostJson<DeleteJobsResult>("/api/v1/jobs/delete", token ?? "", { job_ids: jobIds }),
    onSuccess: async (result) => {
      queryClient.setQueryData<JobSummary[]>(["jobs", token], (jobs) =>
        jobs?.filter((job) => !result.deleted.includes(job.id)),
      );
      await queryClient.invalidateQueries({ queryKey: ["jobs", token] });
      for (const id of result.deleted) queryClient.removeQueries({ queryKey: ["job", token, id] });
    },
  });
}
export const useConnectors = () => useApiQuery<ConnectorSummary[]>("connectors", "/api/v1/connectors");

export function useConnectorRows(name: string | null, page: number, pageSize: number) {
  const token = useAccessToken();
  return useQuery<ConnectorPage, ApiError>({
    queryKey: ["connector-rows", token, name, page, pageSize],
    queryFn: () =>
      apiGet<ConnectorPage>(`/api/v1/connectors/${encodeURIComponent(name ?? "")}/rows?page=${page}&page_size=${pageSize}`, token),
    enabled: Boolean(token && name),
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function useJob(jobId: string | null) {
  const token = useAccessToken();
  return useQuery<JobDetail, ApiError>({
    queryKey: ["job", token, jobId],
    queryFn: () => apiGet<JobDetail>(`/api/v1/jobs/${jobId}`, token),
    enabled: Boolean(token && jobId),
    placeholderData: (previous) => previous,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? POLL_INTERVAL_MS : false;
    },
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function usePending(chatId: string | null) {
  const token = useAccessToken();
  return useQuery<PendingApproval | null, ApiError>({
    queryKey: ["pending", token, chatId],
    queryFn: () => apiGet<PendingApproval | null>(`/api/v1/chats/${chatId}/pending`, token),
    enabled: Boolean(token && chatId),
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function useMessages(chatId: string | null) {
  const token = useAccessToken();
  return useQuery<ChatMessage[], ApiError>({
    queryKey: ["messages", token, chatId],
    queryFn: () => apiGet<ChatMessage[]>(`/api/v1/chats/${chatId}/messages`, token),
    enabled: Boolean(token && chatId),
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}
