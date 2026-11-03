"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiDeleteNoContent, apiDownload, apiGet, apiPatchJson, apiPost, apiPostJson, apiPut, ApiError } from "./api";
import { useAccessToken } from "./auth";
import type {
  ArchivedDeployment,
  ArchivedModel,
  ChatMessage,
  ChatSummary,
  ConnectorPage,
  ConnectorSummary,
  DeleteJobsResult,
  DeleteModelResult,
  Deployment,
  JobDetail,
  JobSummary,
  Me,
  ModelDetail,
  ModelSummary,
  PendingApproval,
  Plan,
  PlanInput,
  PlanRunResult,
  RetrainResult,
} from "./types";

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

const DEPLOYMENT_POLL_MS = 5000;
const DEPLOYMENT_IDLE_POLL_MS = 15_000;

export const useModels = () => useApiQuery<ModelSummary[]>("models", "/api/v1/models");

export const useArchivedModels = () => useApiQuery<ArchivedModel[]>("models-archive", "/api/v1/models/archive");

export function useRestoreModel() {
  const token = useAccessToken();
  const invalidate = useInvalidateModelData();
  return useMutation<ModelDetail, ApiError, string>({
    mutationFn: (modelId) => apiPost<ModelDetail>(`/api/v1/models/${encodeURIComponent(modelId)}/restore`, token ?? ""),
    onSettled: invalidate,
  });
}

export function useDownloadArchivedModel() {
  const token = useAccessToken();
  return useMutation<void, ApiError, { modelId: string; fallbackName: string }>({
    mutationFn: ({ modelId, fallbackName }) =>
      apiDownload(`/api/v1/models/${encodeURIComponent(modelId)}/download`, token ?? "", fallbackName),
  });
}

export function useModel(modelId: string | null) {
  const token = useAccessToken();
  return useQuery<ModelDetail, ApiError>({
    queryKey: ["model", token, modelId],
    queryFn: () => apiGet<ModelDetail>(`/api/v1/models/${encodeURIComponent(modelId ?? "")}`, token),
    enabled: Boolean(token && modelId),
    placeholderData: (previous) => previous,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function useDeployments() {
  const token = useAccessToken();
  return useQuery<Deployment[], ApiError>({
    queryKey: ["deployments", token],
    queryFn: () => apiGet<Deployment[]>("/api/v1/deployments", token),
    enabled: Boolean(token),
    refetchInterval: (query) => {
      const deployments = query.state.data;
      return deployments?.some((deployment) => deployment.status === "provisioning") ? DEPLOYMENT_POLL_MS : DEPLOYMENT_IDLE_POLL_MS;
    },
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function useDeploymentArchive() {
  const token = useAccessToken();
  return useQuery<ArchivedDeployment[], ApiError>({
    queryKey: ["deployments-archive", token],
    queryFn: () => apiGet<ArchivedDeployment[]>("/api/v1/deployments/archive", token),
    enabled: Boolean(token),
    refetchInterval: DEPLOYMENT_IDLE_POLL_MS,
    retry: (failureCount, error) => error.status >= 500 && failureCount < 2,
  });
}

export function useAllocateDeployment() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return useMutation<Deployment, ApiError, { modelId: string; version: number }>({
    mutationFn: ({ modelId, version }) =>
      apiPost<Deployment>(`/api/v1/models/${encodeURIComponent(modelId)}/versions/${version}/deployments`, token ?? ""),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["deployments", token] });
    },
  });
}

export function useDeallocateDeployment() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return useMutation<Deployment, ApiError, string>({
    mutationFn: (depId) => apiPost<Deployment>(`/api/v1/deployments/${depId}/deallocate`, token ?? ""),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["deployments", token] });
    },
  });
}

export function useRetrainVersion() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return useMutation<RetrainResult, ApiError, { modelId: string; version: number }>({
    mutationFn: ({ modelId, version }) =>
      apiPost<RetrainResult>(`/api/v1/models/${encodeURIComponent(modelId)}/versions/${version}/retrain`, token ?? ""),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs", token] }),
        queryClient.invalidateQueries({ queryKey: ["model", token] }),
        queryClient.invalidateQueries({ queryKey: ["models", token] }),
      ]);
    },
  });
}

function useInvalidateModelData() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["models", token] }),
      queryClient.invalidateQueries({ queryKey: ["models-archive", token] }),
      queryClient.invalidateQueries({ queryKey: ["model", token] }),
      queryClient.invalidateQueries({ queryKey: ["deployments", token] }),
      queryClient.invalidateQueries({ queryKey: ["deployments-archive", token] }),
      queryClient.invalidateQueries({ queryKey: ["jobs", token] }),
    ]);
  };
}

export function useDeleteModel() {
  const token = useAccessToken();
  const invalidate = useInvalidateModelData();
  return useMutation<DeleteModelResult, ApiError, { modelId: string; deallocate: boolean }>({
    mutationFn: ({ modelId, deallocate }) =>
      apiDelete<DeleteModelResult>(`/api/v1/models/${encodeURIComponent(modelId)}?deallocate=${deallocate}`, token ?? ""),
    onSettled: invalidate,
  });
}

export function useDeleteVersion() {
  const token = useAccessToken();
  const invalidate = useInvalidateModelData();
  return useMutation<DeleteModelResult, ApiError, { modelId: string; version: number; deallocate: boolean }>({
    mutationFn: ({ modelId, version, deallocate }) =>
      apiDelete<DeleteModelResult>(
        `/api/v1/models/${encodeURIComponent(modelId)}/versions/${version}?deallocate=${deallocate}`,
        token ?? "",
      ),
    onSettled: invalidate,
  });
}

export const usePlans = () => useApiQuery<Plan[]>("plans", "/api/v1/plans");

function useInvalidatePlans() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["plans", token] });
}

export function useCreatePlan() {
  const token = useAccessToken();
  const invalidate = useInvalidatePlans();
  return useMutation<Plan, ApiError, PlanInput>({
    mutationFn: (input) => apiPostJson<Plan>("/api/v1/plans", token ?? "", input),
    onSettled: invalidate,
  });
}

export function useUpdatePlan() {
  const token = useAccessToken();
  const invalidate = useInvalidatePlans();
  return useMutation<Plan, ApiError, { planId: string; changes: Partial<PlanInput> }>({
    mutationFn: ({ planId, changes }) =>
      apiPatchJson<Plan>(`/api/v1/plans/${encodeURIComponent(planId)}`, token ?? "", changes),
    onSettled: invalidate,
  });
}

export function useDeletePlan() {
  const token = useAccessToken();
  const invalidate = useInvalidatePlans();
  return useMutation<void, ApiError, string>({
    mutationFn: (planId) => apiDeleteNoContent(`/api/v1/plans/${encodeURIComponent(planId)}`, token ?? ""),
    onSettled: invalidate,
  });
}

export function useRunPlan() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  return useMutation<PlanRunResult, ApiError, { planId: string; modelName: string }>({
    mutationFn: ({ planId, modelName }) =>
      apiPostJson<PlanRunResult>(`/api/v1/plans/${encodeURIComponent(planId)}/runs`, token ?? "", {
        model_name: modelName,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs", token] }),
        queryClient.invalidateQueries({ queryKey: ["models", token] }),
      ]);
    },
  });
}

export function useSetVersionTag() {
  const token = useAccessToken();
  const invalidate = useInvalidateModelData();
  return useMutation<ModelDetail, ApiError, { modelId: string; version: number; tag: string }>({
    mutationFn: ({ modelId, version, tag }) =>
      apiPut<ModelDetail>(
        `/api/v1/models/${encodeURIComponent(modelId)}/versions/${version}/tags/${encodeURIComponent(tag)}`,
        token ?? "",
      ),
    onSettled: invalidate,
  });
}
