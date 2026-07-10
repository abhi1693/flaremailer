"use client";

import { Activity, ArrowRight, CheckCircle2, CircleX, Clock3, MailCheck, Plus, Send, ShieldBan } from "lucide-react";
import Link from "next/link";
import { EmailTable } from "@/components/features/email-table";
import { useProject } from "@/components/project-provider";
import { ButtonLink } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { formatCompact } from "@/lib/formatters";
import { useEmailsQuery, useMetricsQuery } from "@/lib/queries";

export default function DashboardPage() {
  const { project, projectId, isLoading: projectsLoading } = useProject();
  const metrics = useMetricsQuery(projectId);
  const recent = useEmailsQuery(projectId, { page: 1, pageSize: 6 });

  if (!projectsLoading && !projectId) {
    return (
      <div className="page-container centered-page">
        <EmptyState
          icon={Plus}
          title="Create your first project"
          description="A project is home to your sender domains, templates, keys, and message activity."
          action={<ButtonLink href="/onboarding">Create project</ButtonLink>}
        />
      </div>
    );
  }

  const data = metrics.data;
  const total = data?.total ?? 0;
  const successRate = total ? ((data?.sent ?? 0) / total) * 100 : 0;
  const metricItems = [
    { label: "Messages", value: total, icon: Activity, tone: "ink", note: "All recorded sends" },
    { label: "Sent to provider", value: data?.sent, icon: CheckCircle2, tone: "green", note: `${successRate.toFixed(1)}% accepted by Cloudflare` },
    { label: "In progress", value: (data?.queued ?? 0) + (data?.sending ?? 0), icon: Clock3, tone: "amber", note: "Queued or sending" },
    { label: "Needs attention", value: (data?.failed ?? 0) + (data?.suppressed ?? 0), icon: CircleX, tone: "red", note: "Failed or suppressed" },
  ];

  return (
    <div className="page-container">
      <header className="dashboard-welcome">
        <div><span className="eyebrow">Overview</span><h1>Good to see you.</h1><p>Here’s the latest from <strong>{project?.name ?? "your project"}</strong>.</p></div>
        <ButtonLink href="/compose" icon={Send}>Send an email</ButtonLink>
      </header>

      {metrics.error ? <ErrorState message="Metrics are unavailable right now." onRetry={() => void metrics.refetch()} /> : (
        <section className="metric-grid" aria-label="Message metrics">
          {metricItems.map(({ label, value, icon: Icon, tone, note }) => (
            <Card className="metric-card" key={label}>
              <div className={`metric-icon metric-${tone}`}><Icon size={19} /></div>
              <div className="metric-content"><span>{label}</span>{metrics.isLoading ? <span className="skeleton metric-skeleton" /> : <strong>{formatCompact(value)}</strong>}<small>{note}</small></div>
            </Card>
          ))}
        </section>
      )}

      <section className="dashboard-grid">
        <Card className="recent-card">
          <CardHeader title="Recent activity" description="Your six newest messages." action={<Link className="text-link" href="/activity">View all <ArrowRight size={14} /></Link>} />
          {recent.isLoading ? <SkeletonRows count={5} /> : recent.error ? <ErrorState message="Recent messages could not be loaded." onRetry={() => void recent.refetch()} /> : recent.data?.items.length ? <EmailTable items={recent.data.items} /> : (
            <EmptyState icon={MailCheck} title="No messages yet" description="Send a test email to see activity appear here." action={<ButtonLink href="/compose" variant="secondary" icon={Send}>Compose email</ButtonLink>} />
          )}
        </Card>
        <div className="dashboard-side-stack">
          <Card className="delivery-card">
            <CardHeader title="Provider outcomes" description="Cloudflare acceptance state, not inbox delivery." />
            <div className="outcome-visual">
              <div className="outcome-ring" style={{ "--sent": `${Math.round(successRate)}%` } as React.CSSProperties}>
                <div><strong>{successRate.toFixed(0)}%</strong><span>accepted</span></div>
              </div>
              <ul>
                <li><span className="legend-dot sent" />Sent <strong>{formatCompact(data?.sent)}</strong></li>
                <li><span className="legend-dot queued" />Queued <strong>{formatCompact(data?.queued)}</strong></li>
                <li><span className="legend-dot failed" />Failed <strong>{formatCompact(data?.failed)}</strong></li>
                <li><span className="legend-dot suppressed" />Suppressed <strong>{formatCompact(data?.suppressed)}</strong></li>
              </ul>
            </div>
          </Card>
          <Card className="quick-card">
            <div className="quick-card-art"><ShieldBan size={22} /><MailCheck size={28} /></div>
            <h3>Production controls</h3>
            <p>Review sender domains and API keys before connecting your application.</p>
            <div><Link href="/settings/domains">Sender domains</Link><Link href="/settings/api-keys">API keys</Link></div>
          </Card>
        </div>
      </section>
    </div>
  );
}
