"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Cloud, FolderKanban, Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { ProjectCredentialsCard } from "@/components/features/project-credentials-card";
import { SettingsNav } from "@/components/layout/settings-nav";
import { useProject } from "@/components/project-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate, initials } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import type { Project } from "@/lib/types";

export default function ProjectsSettingsPage() {
  const { projects, project, projectId, setProjectId, isLoading, error, refetch } = useProject();
  const [dialog, setDialog] = useState<"create" | "rename" | "delete" | null>(null);
  const [selected, setSelected] = useState<Project>();
  const [name, setName] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();

  const close = () => {
    setDialog(null);
    setSelected(undefined);
    setName("");
  };
  const mutation = useMutation({
    mutationFn: async () => {
      if (dialog === "create") return api.projects.create({ name });
      if (dialog === "rename") return api.projects.update(selected!.id, { name });
      await api.projects.remove(selected!.id);
      return undefined;
    },
    onSuccess: async (result) => {
      if (dialog === "create" && result) setProjectId(result.id);
      toast(dialog === "delete" ? "Project deleted." : dialog === "rename" ? "Project renamed." : "Project created.", "success");
      close();
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
    onError: (mutationError) => toast(getErrorMessage(mutationError), "error"),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }
  function openRename(item: Project) {
    setSelected(item);
    setName(item.name);
    setDialog("rename");
  }
  function openCredentials(id: string) {
    setProjectId(id);
    window.requestAnimationFrame(() => {
      document.getElementById("project-credentials")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <div className="page-container">
      <PageHeader
        eyebrow="Settings"
        title="Projects"
        description="Keep applications isolated with separate sending credentials, keys, and activity."
        actions={<Button icon={Plus} onClick={() => setDialog("create")}>New project</Button>}
      />
      <SettingsNav />
      {isLoading ? <SkeletonRows count={4} /> : error ? (
        <ErrorState message="Projects could not be loaded." onRetry={refetch} />
      ) : projects.length ? (
        <div className="settings-list">
          {projects.map((item) => (
            <Card className={`settings-row ${item.id === projectId ? "current" : ""}`} key={item.id}>
              <span className="settings-row-icon project-color">{initials(item.name)}</span>
              <div className="settings-row-main">
                <div><h2>{item.name}</h2>{item.id === projectId ? <span className="current-chip">Current</span> : null}</div>
                <p><code>{item.slug}</code> · Created {formatDate(item.created_at, { dateStyle: "medium" })}</p>
              </div>
              <div className="settings-row-actions">
                <Button variant="ghost" size="sm" icon={Cloud} onClick={() => openCredentials(item.id)}>Sending</Button>
                {item.id !== projectId ? <Button variant="ghost" size="sm" onClick={() => setProjectId(item.id)}>Switch</Button> : null}
                <Button variant="ghost" size="icon" onClick={() => openRename(item)} aria-label={`Rename ${item.name}`}><Pencil size={16} /></Button>
                <Button variant="ghost" size="icon" onClick={() => { setSelected(item); setDialog("delete"); }} aria-label={`Delete ${item.name}`}><Trash2 size={16} /></Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card><EmptyState icon={FolderKanban} title="No projects" description="Create a project to organize your sending configuration." action={<Button icon={Plus} onClick={() => setDialog("create")}>Create project</Button>} /></Card>
      )}

      {!isLoading && !error ? <ProjectCredentialsCard project={project} /> : null}

      <Dialog
        open={dialog === "create" || dialog === "rename"}
        onClose={close}
        title={dialog === "rename" ? "Rename project" : "Create a project"}
        description="Projects isolate sending credentials, domains, templates, keys, and activity."
        footer={<><Button variant="ghost" onClick={close}>Cancel</Button><Button loading={mutation.isPending} disabled={!name.trim()} onClick={() => mutation.mutate()}>{dialog === "rename" ? "Save name" : "Create project"}</Button></>}
      >
        <form onSubmit={submit}>
          <Field label="Project name"><Input autoFocus required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="Acme Production" /></Field>
          <button className="sr-only" type="submit">Save project</button>
        </form>
      </Dialog>
      <Dialog
        open={dialog === "delete"}
        onClose={close}
        title="Delete project?"
        description="This permanently removes its credentials, domains, templates, suppressions, keys, and email history."
        footer={<><Button variant="ghost" onClick={close}>Cancel</Button><Button variant="danger" icon={Trash2} loading={mutation.isPending} onClick={() => mutation.mutate()}>Delete project</Button></>}
      >
        <p>Delete <strong>{selected?.name}</strong>? This action cannot be undone.</p>
      </Dialog>
    </div>
  );
}
