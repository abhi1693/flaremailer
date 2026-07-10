"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Code2, FileText, MoreHorizontal, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useProject } from "@/components/project-provider";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useTemplatesQuery } from "@/lib/queries";
import type { Template } from "@/lib/types";

export default function TemplatesPage() {
  const { projectId } = useProject();
  const templates = useTemplatesQuery(projectId);
  const [removing, setRemoving] = useState<Template>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const remove = useMutation({
    mutationFn: () => api.templates.remove(projectId!, removing!.id),
    onSuccess: async () => { setRemoving(undefined); toast("Template deleted.", "success"); await queryClient.invalidateQueries({ queryKey: queryKeys.templates(projectId) }); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });

  return (
    <div className="page-container">
      <PageHeader eyebrow="Reusable content" title="Templates" description="Build server-rendered email content with safe variable placeholders." actions={<ButtonLink href="/templates/new" icon={Plus}>New template</ButtonLink>} />
      {templates.isLoading ? <SkeletonRows count={5} /> : templates.error ? <ErrorState message="Templates could not be loaded." onRetry={() => void templates.refetch()} /> : templates.data?.items.length ? (
        <div className="template-grid">
          {templates.data.items.map((template) => (
            <Card className="template-card" key={template.id}>
              <div className="template-card-top"><span className="template-file-icon"><FileText size={19} /></span><button className="icon-button" onClick={() => setRemoving(template)} aria-label={`Delete ${template.name}`}><MoreHorizontal size={19} /></button></div>
              <Link href={`/templates/${template.id}`}><h2>{template.name}</h2><p>{template.subject}</p></Link>
              <div className="template-card-tags"><span><Code2 size={13} />{template.html ? "HTML" : "Text"}</span><code>{template.slug}</code></div>
              <footer><span>Updated {formatDate(template.updated_at, { dateStyle: "medium" })}</span><Link href={`/templates/${template.id}`}>Edit</Link></footer>
            </Card>
          ))}
        </div>
      ) : <Card><EmptyState icon={FileText} title="No templates yet" description="Create reusable content for receipts, sign-ins, alerts, and more." action={<ButtonLink href="/templates/new" icon={Plus}>Create template</ButtonLink>} /></Card>}
      <Dialog open={Boolean(removing)} onClose={() => setRemoving(undefined)} title="Delete template?" description="Existing message activity is preserved, but this template cannot be used again." footer={<><Button variant="ghost" onClick={() => setRemoving(undefined)}>Cancel</Button><Button variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate()}>Delete template</Button></>}><p>Delete <strong>{removing?.name}</strong>? This action cannot be undone.</p></Dialog>
    </div>
  );
}
