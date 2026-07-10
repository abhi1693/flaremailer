import { apiKeysCreate, apiKeysList, apiKeysRevoke } from "@/generated/api-keys/api-keys";
import { authGetCurrentUser, authLogin, authLogout, authRegister } from "@/generated/auth/auth";
import { domainsCreate, domainsDelete, domainsList, domainsUpdate } from "@/generated/domains/domains";
import { emailsEnqueue, emailsGet, emailsList, emailsResend } from "@/generated/emails/emails";
import { metricsGet } from "@/generated/metrics/metrics";
import {
  projectCredentialsDelete,
  projectCredentialsGet,
  projectCredentialsUpsert,
} from "@/generated/project-credentials/project-credentials";
import { projectsCreate, projectsDelete, projectsList, projectsUpdate } from "@/generated/projects/projects";
import { suppressionsCreate, suppressionsDelete, suppressionsList } from "@/generated/suppressions/suppressions";
import {
  templatesCreate,
  templatesDelete,
  templatesGet,
  templatesList,
  templatesPreview,
  templatesUpdate,
} from "@/generated/templates/templates";
import type {
  ApiKeyCreatedResponse,
  ApiKeyListResponse,
  AuthResponse,
  DomainCreate,
  DomainListResponse,
  DomainResponse,
  DomainUpdate,
  EmailCreate,
  EmailDetailResponse,
  EmailEnqueueResponse,
  EmailListResponse,
  EmailsListStatus,
  MetricsResponse,
  ProjectCredentialsResponse,
  ProjectCredentialsWrite,
  ProjectListResponse,
  ProjectResponse,
  SuppressionListResponse,
  SuppressionResponse,
  TemplateCreate,
  TemplateListResponse,
  TemplatePreviewResponse,
  TemplateResponse,
  TemplateUpdate,
  UserResponse,
} from "@/generated/models";

type GeneratedResponse<T> = { data: T; status: number; headers: Headers };
const data = <T>(response: unknown) => (response as GeneratedResponse<T>).data;

export const api = {
  auth: {
    me: async (): Promise<UserResponse> => data<AuthResponse>(await authGetCurrentUser()).user,
    login: async (input: { email: string; password: string }): Promise<UserResponse> =>
      data<AuthResponse>(await authLogin(input)).user,
    register: async (input: { email: string; password: string }): Promise<UserResponse> =>
      data<AuthResponse>(await authRegister(input)).user,
    logout: async (): Promise<void> => {
      await authLogout();
    },
  },
  projects: {
    list: async (): Promise<ProjectListResponse> => data<ProjectListResponse>(await projectsList()),
    create: async (input: { name: string }): Promise<ProjectResponse> =>
      data<ProjectResponse>(await projectsCreate(input)),
    update: async (id: string, input: { name: string }): Promise<ProjectResponse> =>
      data<ProjectResponse>(await projectsUpdate(id, input)),
    remove: async (id: string): Promise<void> => {
      await projectsDelete(id);
    },
  },
  projectCredentials: {
    get: async (projectId: string): Promise<ProjectCredentialsResponse> =>
      data<ProjectCredentialsResponse>(await projectCredentialsGet(projectId)),
    upsert: async (projectId: string, input: ProjectCredentialsWrite): Promise<ProjectCredentialsResponse> =>
      data<ProjectCredentialsResponse>(await projectCredentialsUpsert(projectId, input)),
    remove: async (projectId: string): Promise<void> => {
      await projectCredentialsDelete(projectId);
    },
  },
  metrics: {
    get: async (projectId: string): Promise<MetricsResponse> =>
      data<MetricsResponse>(await metricsGet({ project_id: projectId })),
  },
  emails: {
    list: async (input: {
      projectId: string;
      search?: string;
      status?: EmailsListStatus;
      page?: number;
      pageSize?: number;
    }): Promise<EmailListResponse> =>
      data<EmailListResponse>(
        await emailsList({
          project_id: input.projectId,
          search: input.search || undefined,
          status: input.status,
          limit: input.pageSize ?? 20,
          offset: ((input.page ?? 1) - 1) * (input.pageSize ?? 20),
        }),
      ),
    get: async (projectId: string, id: string): Promise<EmailDetailResponse> =>
      data<EmailDetailResponse>(await emailsGet(id, { project_id: projectId })),
    send: async (input: EmailCreate): Promise<EmailEnqueueResponse> =>
      data<EmailEnqueueResponse>(await emailsEnqueue(input)),
    resend: async (projectId: string, id: string): Promise<EmailEnqueueResponse> =>
      data<EmailEnqueueResponse>(await emailsResend(id, { project_id: projectId })),
  },
  templates: {
    list: async (projectId: string): Promise<TemplateListResponse> =>
      data<TemplateListResponse>(await templatesList(projectId)),
    get: async (projectId: string, id: string): Promise<TemplateResponse> =>
      data<TemplateResponse>(await templatesGet(projectId, id)),
    create: async (projectId: string, input: TemplateCreate): Promise<TemplateResponse> =>
      data<TemplateResponse>(await templatesCreate(projectId, input)),
    update: async (projectId: string, id: string, input: TemplateUpdate): Promise<TemplateResponse> =>
      data<TemplateResponse>(await templatesUpdate(projectId, id, input)),
    remove: async (projectId: string, id: string): Promise<void> => {
      await templatesDelete(projectId, id);
    },
    preview: async (projectId: string, id: string, variables: Record<string, unknown>): Promise<TemplatePreviewResponse> =>
      data<TemplatePreviewResponse>(await templatesPreview(projectId, id, { variables })),
  },
  suppressions: {
    list: async (projectId: string, search?: string): Promise<SuppressionListResponse> =>
      data<SuppressionListResponse>(await suppressionsList(projectId, { search: search || undefined })),
    create: async (projectId: string, input: { email: string; reason?: string }): Promise<SuppressionResponse> =>
      data<SuppressionResponse>(await suppressionsCreate(projectId, { email: input.email, reason: input.reason ?? "manual" })),
    remove: async (projectId: string, id: string): Promise<void> => {
      await suppressionsDelete(projectId, id);
    },
  },
  domains: {
    list: async (projectId: string): Promise<DomainListResponse> =>
      data<DomainListResponse>(await domainsList(projectId)),
    create: async (projectId: string, domain: string, options?: Pick<DomainCreate, "verified" | "active">): Promise<DomainResponse> =>
      data<DomainResponse>(await domainsCreate(projectId, { domain, ...options })),
    update: async (projectId: string, id: string, input: DomainUpdate): Promise<DomainResponse> =>
      data<DomainResponse>(await domainsUpdate(projectId, id, input)),
    remove: async (projectId: string, id: string): Promise<void> => {
      await domainsDelete(projectId, id);
    },
  },
  apiKeys: {
    list: async (projectId: string): Promise<ApiKeyListResponse> =>
      data<ApiKeyListResponse>(await apiKeysList(projectId)),
    create: async (projectId: string, name: string): Promise<ApiKeyCreatedResponse> =>
      data<ApiKeyCreatedResponse>(await apiKeysCreate(projectId, { name })),
    revoke: async (projectId: string, id: string): Promise<void> => {
      await apiKeysRevoke(projectId, id);
    },
  },
};
