"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useProjectsQuery } from "@/lib/queries";
import type { Project } from "@/lib/types";

interface ProjectContextValue {
  projects: Project[];
  project?: Project;
  projectId?: string;
  setProjectId: (projectId: string) => void;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);
const storageKey = "flaremailer.project";

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { data, isLoading, error, refetch } = useProjectsQuery();
  const projects = useMemo(() => data?.items ?? [], [data?.items]);
  const [selected, setSelected] = useState<string | undefined>(() =>
    typeof window === "undefined" ? undefined : window.localStorage.getItem(storageKey) ?? undefined,
  );

  const project = projects.find((item) => item.id === selected) ?? projects[0];

  useEffect(() => {
    if (project?.id) window.localStorage.setItem(storageKey, project.id);
  }, [project?.id]);

  const value = useMemo<ProjectContextValue>(
    () => ({
      projects,
      project,
      projectId: project?.id,
      setProjectId(projectId) {
        setSelected(projectId);
        window.localStorage.setItem(storageKey, projectId);
      },
      isLoading,
      error,
      refetch: () => void refetch(),
    }),
    [error, isLoading, project, projects, refetch],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const value = useContext(ProjectContext);
  if (!value) throw new Error("useProject must be used inside ProjectProvider");
  return value;
}
