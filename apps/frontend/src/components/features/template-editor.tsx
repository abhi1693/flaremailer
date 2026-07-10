"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Braces, Eye, Save, Text } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useProject } from "@/components/project-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { queryKeys } from "@/lib/query-keys";
import type { Template } from "@/lib/types";

const starterHtml = `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #17211f;">
  <h1>Hello {{ name }}</h1>
  <p style="line-height: 1.6; color: #596461;">Your message goes here.</p>
</div>`;

export function TemplateEditor({ template }: { template?: Template }) {
  const editing = Boolean(template);
  const { projectId } = useProject();
  const router = useRouter();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [mode, setMode] = useState<"html" | "text">("html");
  const [variables, setVariables] = useState('{"name":"Ada"}');
  const [rendered, setRendered] = useState<{ subject: string; html: string | null; text: string | null }>();
  const [values, setValues] = useState(() => template
    ? { name: template.name, slug: template.slug, subject: template.subject, html: template.html ?? "", text: template.text ?? "" }
    : { name: "", slug: "", subject: "Hello {{ name }}", html: starterHtml, text: "Hello {{ name }}\n\nYour message goes here." });

  const save = useMutation({
    mutationFn: () => {
      if (!projectId) throw new Error("Create a project first.");
      return editing
        ? api.templates.update(projectId, template!.id, { name: values.name, subject: values.subject, html: values.html || null, text: values.text || null })
        : api.templates.create(projectId, { name: values.name, slug: values.slug || null, subject: values.subject, html: values.html || null, text: values.text || null });
    },
    onSuccess: async (result) => {
      toast(editing ? "Template updated." : "Template created.", "success");
      await queryClient.invalidateQueries({ queryKey: queryKeys.templates(projectId) });
      router.replace(`/templates/${result.id}`);
    },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const preview = useMutation({
    mutationFn: async () => {
      const parsed = JSON.parse(variables) as Record<string, unknown>;
      if (editing && projectId) return api.templates.preview(projectId, template!.id, parsed);
      const render = (source: string) => source.replace(/{{\s*([\w.]+)\s*}}/g, (_, key: string) => String(parsed[key] ?? `{{ ${key} }}`));
      return { subject: render(values.subject), html: values.html ? render(values.html) : null, text: values.text ? render(values.text) : null };
    },
    onSuccess: setRendered,
    onError: (error) => toast(getErrorMessage(error), "error"),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }
  const previewData = rendered ?? { subject: values.subject, html: values.html, text: values.text };

  return (
    <div className="template-editor-page">
      <Link href="/templates" className="back-link"><ArrowLeft size={16} />Back to templates</Link>
      <header className="editor-page-header"><div><span className="eyebrow">{editing ? template?.slug : "New template"}</span><h1>{editing ? template?.name : "Create a template"}</h1><p>Use simple <code>{"{{ variable }}"}</code> placeholders for safe server-side rendering.</p></div><Button icon={Save} loading={save.isPending} onClick={() => save.mutate()} disabled={!values.name || !values.subject}>Save template</Button></header>
      <form className="template-editor-grid" onSubmit={submit}>
        <Card className="template-fields-card">
          <div className="form-grid two-col">
            <Field label="Template name"><Input required value={values.name} onChange={(event) => setValues({ ...values, name: event.target.value })} placeholder="Welcome email" /></Field>
            <Field label="Slug" optional hint={editing ? "Slugs cannot be changed." : "Generated from the name if blank."}><Input disabled={editing} value={values.slug} onChange={(event) => setValues({ ...values, slug: event.target.value })} placeholder="welcome-email" /></Field>
          </div>
          <Field label="Subject"><Input required value={values.subject} onChange={(event) => setValues({ ...values, subject: event.target.value })} /></Field>
          <div className="editor-tabs"><button type="button" className={mode === "html" ? "active" : ""} onClick={() => setMode("html")}><Braces size={15} />HTML</button><button type="button" className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}><Text size={15} />Plain text</button></div>
          <Field label={mode === "html" ? "HTML content" : "Plain-text content"}>
            <Textarea required={!values[mode === "html" ? "text" : "html"]} className="code-input template-code-editor" rows={24} value={values[mode]} onChange={(event) => setValues({ ...values, [mode]: event.target.value })} spellCheck={false} />
          </Field>
          {save.error ? <div className="inline-error" role="alert">{getErrorMessage(save.error)}</div> : null}
          <button type="submit" className="sr-only">Save template</button>
        </Card>
        <div className="template-preview-column">
          <Card className="variables-card">
            <div className="mini-card-head"><div><h2>Preview variables</h2><p>JSON values used only for this preview.</p></div><Button type="button" size="sm" variant="secondary" icon={Eye} loading={preview.isPending} onClick={() => preview.mutate()}>Render</Button></div>
            <Textarea className="code-input" rows={5} value={variables} onChange={(event) => setVariables(event.target.value)} spellCheck={false} />
          </Card>
          <Card className="template-live-preview">
            <div className="preview-toolbar"><div><Eye size={16} /><strong>Preview</strong></div><span>Sandboxed</span></div>
            <div className="template-subject-preview"><span>Subject</span><strong>{previewData.subject}</strong></div>
            <div className="template-preview-frame">{previewData.html ? <iframe title="Template preview" sandbox="" referrerPolicy="no-referrer" srcDoc={previewData.html} /> : <pre>{previewData.text || "No content"}</pre>}</div>
          </Card>
        </div>
      </form>
    </div>
  );
}
