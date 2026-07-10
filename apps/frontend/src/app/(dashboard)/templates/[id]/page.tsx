"use client";

import { useParams } from "next/navigation";
import { TemplateEditor } from "@/components/features/template-editor";
import { useProject } from "@/components/project-provider";
import { ErrorState, PageLoader } from "@/components/ui/states";
import { useTemplateQuery } from "@/lib/queries";

export default function EditTemplatePage() {
  const { id } = useParams<{ id: string }>();
  const { projectId } = useProject();
  const template = useTemplateQuery(projectId, id);
  if (template.isLoading) return <div className="page-container"><PageLoader label="Loading template" /></div>;
  if (template.error || !template.data) return <div className="page-container"><ErrorState message="This template could not be found." onRetry={() => void template.refetch()} /></div>;
  return <div className="page-container"><TemplateEditor key={template.data.id} template={template.data} /></div>;
}
