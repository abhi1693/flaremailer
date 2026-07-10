"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Braces, CalendarClock, Mail, RefreshCw, Server, Text } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useProject } from "@/components/project-provider";
import { Card, CardHeader } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { ErrorState, PageLoader } from "@/components/ui/states";
import { StatusBadge } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate, mailboxLabel, recipientOf } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useEmailQuery } from "@/lib/queries";

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { projectId } = useProject();
  const [preview, setPreview] = useState<"html" | "text">("html");
  const message = useEmailQuery(projectId, id);
  const queryClient = useQueryClient();
  const toast = useToast();
  const resend = useMutation({
    mutationFn: () => api.emails.resend(projectId!, id),
    onSuccess: async () => {
      toast("Email queued again.", "success");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.email(id) }),
        queryClient.invalidateQueries({ queryKey: ["emails"] }),
      ]);
    },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });

  if (message.isLoading) return <div className="page-container"><PageLoader label="Loading message" /></div>;
  if (message.error || !message.data) return <div className="page-container"><ErrorState message="This message could not be found." onRetry={() => void message.refetch()} /></div>;
  const email = message.data;
  const canResend = email.status !== "queued" && email.status !== "sending";

  return (
    <div className="page-container detail-page">
      <Link href="/activity" className="back-link"><ArrowLeft size={16} /> Back to activity</Link>
      <header className="message-header">
        <div><StatusBadge status={email.status} /><h1>{email.subject || "(No subject)"}</h1><p>To {recipientOf(email)}</p></div>
        <div className="page-actions"><CopyButton value={email.id} label="Copy ID" />{canResend ? <Button icon={RefreshCw} loading={resend.isPending} onClick={() => resend.mutate()}>Resend</Button> : null}</div>
      </header>
      {email.error_message ? <div className="failure-banner" role="alert"><strong>Latest delivery attempt failed</strong><span>{email.error_message}</span></div> : null}
      <section className="message-detail-grid">
        <Card className="preview-card">
          <CardHeader title="Message preview" description="Isolated in a sandboxed frame." action={
            <div className="segmented-control">
              <button className={preview === "html" ? "active" : ""} onClick={() => setPreview("html")}><Braces size={14} />HTML</button>
              <button className={preview === "text" ? "active" : ""} onClick={() => setPreview("text")}><Text size={14} />Text</button>
            </div>
          } />
          <div className="preview-surface">
            {preview === "html" && email.html ? (
              <iframe title="Email HTML preview" sandbox="" referrerPolicy="no-referrer" srcDoc={email.html} />
            ) : (
              <pre>{email.text || "No plain-text body was supplied."}</pre>
            )}
          </div>
        </Card>
        <aside className="message-meta-stack">
          <Card className="meta-card">
            <h2>Details</h2>
            <dl>
              <div><dt><Mail size={15} />From</dt><dd>{email.from_email || "—"}</dd></div>
              <div><dt><CalendarClock size={15} />Created</dt><dd>{formatDate(email.created_at)}</dd></div>
              <div><dt><RefreshCw size={15} />Attempts</dt><dd>{email.attempt_count}</dd></div>
              <div><dt><Server size={15} />Provider ID</dt><dd className="code-value">{email.provider_message_id || "—"}{email.provider_message_id ? <CopyButton variant="ghost" value={email.provider_message_id} label="" /> : null}</dd></div>
            </dl>
          </Card>
          <Card className="meta-card">
            <h2>Envelope</h2>
            <dl>
              <div><dt>To</dt><dd>{recipientOf(email)}</dd></div>
              {email.cc?.length ? <div><dt>CC</dt><dd>{email.cc.map(mailboxLabel).join(", ")}</dd></div> : null}
              {email.reply_to ? <div><dt>Reply to</dt><dd>{mailboxLabel(email.reply_to)}</dd></div> : null}
              <div><dt>Message ID</dt><dd className="code-value">{email.id}</dd></div>
              {email.tags.length ? <div><dt>Tags</dt><dd>{email.tags.join(", ")}</dd></div> : null}
            </dl>
          </Card>
          {email.attempts.length ? (
            <Card className="meta-card attempt-card">
              <h2>Delivery attempts</h2>
              <ol className="attempt-list">
                {email.attempts.map((attempt) => (
                  <li key={attempt.attempt_number}>
                    <span>{attempt.attempt_number}</span>
                    <div><strong>{attempt.status}</strong><small>{formatDate(attempt.started_at)}</small>{attempt.error_message ? <p>{attempt.error_message}</p> : null}</div>
                  </li>
                ))}
              </ol>
            </Card>
          ) : null}
        </aside>
      </section>
    </div>
  );
}
