export const queryKeys = {
  me: ["me"] as const,
  projects: ["projects"] as const,
  projectCredentials: (projectId?: string) => ["projectCredentials", projectId] as const,
  metrics: (projectId?: string) => ["metrics", projectId] as const,
  emails: (projectId?: string, filters?: object) => ["emails", projectId, filters] as const,
  email: (id: string) => ["email", id] as const,
  templates: (projectId?: string) => ["templates", projectId] as const,
  template: (projectId?: string, id?: string) => ["template", projectId, id] as const,
  suppressions: (projectId?: string, search?: string) => ["suppressions", projectId, search] as const,
  domains: (projectId?: string) => ["domains", projectId] as const,
  apiKeys: (projectId?: string) => ["apiKeys", projectId] as const,
};
