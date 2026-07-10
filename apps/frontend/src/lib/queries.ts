"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { EmailStatus } from "@/lib/types";

export function useSessionQuery(enabled = true) {
  return useQuery({ queryKey: queryKeys.me, queryFn: api.auth.me, enabled, retry: false });
}

export function useProjectsQuery() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: api.projects.list });
}

export function useProjectCredentialsQuery(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.projectCredentials(projectId),
    queryFn: () => api.projectCredentials.get(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useMetricsQuery(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.metrics(projectId),
    queryFn: () => api.metrics.get(projectId!),
    enabled: Boolean(projectId),
    refetchInterval: projectId ? 15_000 : false,
  });
}

export function useEmailsQuery(
  projectId?: string,
  filters: { search?: string; status?: EmailStatus; page?: number; pageSize?: number } = {},
) {
  return useQuery({
    queryKey: queryKeys.emails(projectId, filters),
    queryFn: () => api.emails.list({ projectId: projectId!, ...filters }),
    enabled: Boolean(projectId),
    refetchInterval: projectId ? 10_000 : false,
  });
}

export function useEmailQuery(projectId: string | undefined, id: string) {
  return useQuery({
    queryKey: queryKeys.email(id),
    queryFn: () => api.emails.get(projectId!, id),
    enabled: Boolean(projectId && id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "sending" ? 3_000 : false;
    },
  });
}

export function useTemplatesQuery(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.templates(projectId),
    queryFn: () => api.templates.list(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useTemplateQuery(projectId: string | undefined, id: string) {
  return useQuery({
    queryKey: queryKeys.template(projectId, id),
    queryFn: () => api.templates.get(projectId!, id),
    enabled: Boolean(projectId && id),
  });
}

export function useSuppressionsQuery(projectId?: string, search?: string) {
  return useQuery({
    queryKey: queryKeys.suppressions(projectId, search),
    queryFn: () => api.suppressions.list(projectId!, search),
    enabled: Boolean(projectId),
  });
}

export function useDomainsQuery(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.domains(projectId),
    queryFn: () => api.domains.list(projectId!),
    enabled: Boolean(projectId),
  });
}

export function useApiKeysQuery(projectId?: string) {
  return useQuery({
    queryKey: queryKeys.apiKeys(projectId),
    queryFn: () => api.apiKeys.list(projectId!),
    enabled: Boolean(projectId),
  });
}
