"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Braces, CheckCircle2, ChevronDown, Code2, Eye, Mail, Send, Settings2, Text } from "lucide-react";
import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { useProject } from "@/components/project-provider";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { splitEmails } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useDomainsQuery, useTemplatesQuery } from "@/lib/queries";

const initialHtml = `<div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 32px; color: #17211f;">
  <h1 style="font-size: 24px; margin: 0 0 16px;">Hello from Flaremailer</h1>
  <p style="line-height: 1.65; color: #58635f;">Your transactional email pipeline is ready to use.</p>
</div>`;

export default function ComposePage() {
  const { projectId } = useProject();
  const domains = useDomainsQuery(projectId);
  const templates = useTemplatesQuery(projectId);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [sent, setSent] = useState<{ id: string }>();
  const [advanced, setAdvanced] = useState(false);
  const [bodyMode, setBodyMode] = useState<"html" | "text">("html");
  const [values, setValues] = useState({
    from_email: "",
    from_name: "",
    to: "",
    cc: "",
    bcc: "",
    reply_to: "",
    subject: "Test from Flaremailer",
    html_body: initialHtml,
    text_body: "Hello from Flaremailer\n\nYour transactional email pipeline is ready to use.",
    template_id: "",
    variables: "{}",
    tags: "test",
  });

  const verifiedDomains = (domains.data?.items ?? []).filter((domain) => domain.verified && domain.active);
  const senderOptions = useMemo(() => verifiedDomains.map((domain) => `hello@${domain.domain}`), [verifiedDomains]);
  const selectedTemplate = templates.data?.items.find((template) => template.id === values.template_id);
  const previewHtml = selectedTemplate?.html ?? values.html_body;
  const previewText = selectedTemplate?.text ?? values.text_body;
  const sendEmail = useMutation({
    mutationFn: () => {
      if (!projectId) throw new Error("Create a project before sending.");
      let variables: Record<string, string> | undefined;
      if (values.template_id) {
        const parsed = JSON.parse(values.variables) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Variables must be a JSON object.");
        variables = parsed as Record<string, string>;
      }
      return api.emails.send({
        project_id: projectId,
        from: { email: values.from_email, name: values.from_name || undefined },
        to: splitEmails(values.to).map((email) => ({ email })),
        cc: splitEmails(values.cc).map((email) => ({ email })),
        bcc: splitEmails(values.bcc).map((email) => ({ email })),
        reply_to: values.reply_to ? { email: values.reply_to } : undefined,
        ...(values.template_id
          ? { template_id: values.template_id, variables }
          : { subject: values.subject, html: values.html_body, text: values.text_body }),
        tags: splitEmails(values.tags),
      });
    },
    onSuccess: async (result) => {
      setSent(result);
      toast("Email accepted and queued.", "success");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["emails"] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.metrics(projectId) }),
      ]);
    },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setSent(undefined);
    sendEmail.mutate();
  }

  const update = (key: keyof typeof values, value: string) => setValues((current) => ({ ...current, [key]: value }));

  return (
    <div className="page-container compose-page">
      <PageHeader eyebrow="Test delivery" title="Compose an email" description="Send a single transactional message through your Cloudflare pipeline." />
      {!verifiedDomains.length && !domains.isLoading ? (
        <div className="notice-banner"><Mail size={19} /><div><strong>Add a verified sender domain first</strong><span>Sending is gated until your project has an active sender domain.</span></div><ButtonLink href="/settings/domains" variant="secondary" size="sm">Add domain</ButtonLink></div>
      ) : null}
      <form onSubmit={submit} className="compose-grid">
        <Card className="compose-form-card">
          <div className="form-section">
            <div className="section-heading"><span>01</span><div><h2>Envelope</h2><p>Who the message is from and where it should go.</p></div></div>
            <div className="form-grid two-col">
              <Field label="From address">
                <Input list="sender-addresses" required type="email" value={values.from_email} onChange={(event) => update("from_email", event.target.value)} placeholder={senderOptions[0] ?? "hello@example.com"} />
                <datalist id="sender-addresses">{senderOptions.map((email) => <option key={email} value={email} />)}</datalist>
              </Field>
              <Field label="From name" optional><Input value={values.from_name} onChange={(event) => update("from_name", event.target.value)} placeholder="Acme" /></Field>
            </div>
            <Field label="To" hint="Separate multiple addresses with commas."><Input required type="text" value={values.to} onChange={(event) => update("to", event.target.value)} placeholder="customer@example.com" /></Field>
            <button className="advanced-toggle" type="button" onClick={() => setAdvanced((value) => !value)} aria-expanded={advanced}><Settings2 size={15} />{advanced ? "Hide" : "Show"} CC, BCC, reply-to, and tags <ChevronDown size={14} className={advanced ? "rotate" : ""} /></button>
            {advanced ? <div className="advanced-fields">
              <div className="form-grid two-col"><Field label="CC" optional><Input value={values.cc} onChange={(event) => update("cc", event.target.value)} placeholder="team@example.com" /></Field><Field label="BCC" optional><Input value={values.bcc} onChange={(event) => update("bcc", event.target.value)} placeholder="audit@example.com" /></Field></div>
              <div className="form-grid two-col"><Field label="Reply to" optional><Input type="email" value={values.reply_to} onChange={(event) => update("reply_to", event.target.value)} placeholder="support@example.com" /></Field><Field label="Tags" optional hint="Comma separated"><Input value={values.tags} onChange={(event) => update("tags", event.target.value)} placeholder="receipt, production" /></Field></div>
            </div> : null}
          </div>
          <div className="form-section">
            <div className="section-heading"><span>02</span><div><h2>Content</h2><p>Use a saved template or write the message here.</p></div></div>
            <Field label="Template" optional hint="Leave blank to compose directly.">
              <Select value={values.template_id} onChange={(event) => update("template_id", event.target.value)}><option value="">No template — write directly</option>{templates.data?.items.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</Select>
            </Field>
            {values.template_id ? (
              <Field label="Template variables" hint='A JSON object, for example {"name":"Ada"}'><Textarea className="code-input" rows={7} value={values.variables} onChange={(event) => update("variables", event.target.value)} spellCheck={false} /></Field>
            ) : (
              <>
                <Field label="Subject"><Input required value={values.subject} onChange={(event) => update("subject", event.target.value)} placeholder="Your receipt is ready" /></Field>
                <div className="editor-tabs"><button type="button" className={bodyMode === "html" ? "active" : ""} onClick={() => setBodyMode("html")}><Code2 size={15} />HTML</button><button type="button" className={bodyMode === "text" ? "active" : ""} onClick={() => setBodyMode("text")}><Text size={15} />Plain text</button></div>
                <Field label={bodyMode === "html" ? "HTML body" : "Plain-text body"}>
                  <Textarea className="code-input compose-editor" rows={14} value={bodyMode === "html" ? values.html_body : values.text_body} onChange={(event) => update(bodyMode === "html" ? "html_body" : "text_body", event.target.value)} spellCheck={false} />
                </Field>
              </>
            )}
          </div>
          {sendEmail.error ? <div className="inline-error" role="alert">{getErrorMessage(sendEmail.error)}</div> : null}
          {sent ? <div className="success-banner"><CheckCircle2 size={20} /><div><strong>Email queued</strong><span>Message {sent.id} is now in activity.</span></div><Link href={`/activity/${sent.id}`}>View message</Link></div> : null}
          <div className="compose-actions"><span>One recipient or a short test list works best here.</span><Button size="lg" icon={Send} type="submit" loading={sendEmail.isPending} disabled={!projectId || !values.from_email || !values.to}>Send email</Button></div>
        </Card>
        <Card className="compose-preview-card">
          <div className="preview-toolbar"><div><Eye size={16} /><strong>Preview</strong></div><span>{selectedTemplate ? selectedTemplate.name : "Draft"}</span></div>
          <div className="mock-email">
            <div className="mock-email-head"><div><span>From</span><strong>{values.from_name || "Sender"} &lt;{values.from_email || "hello@example.com"}&gt;</strong></div><div><span>To</span><strong>{values.to || "customer@example.com"}</strong></div><h3>{selectedTemplate?.subject || values.subject || "No subject"}</h3></div>
            <div className="mock-email-body">{previewHtml ? <iframe title="Draft HTML preview" sandbox="" referrerPolicy="no-referrer" srcDoc={previewHtml} /> : <pre>{previewText}</pre>}</div>
          </div>
          <p className="preview-note"><Braces size={14} />Template variables render on the server when the email is queued.</p>
        </Card>
      </form>
    </div>
  );
}
