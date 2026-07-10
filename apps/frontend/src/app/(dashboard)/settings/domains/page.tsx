"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Cloud, Globe2, Plus, Trash2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
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
import { formatDate } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useDomainsQuery } from "@/lib/queries";
import type { SenderDomain } from "@/lib/types";

export default function DomainsSettingsPage() {
  const { projectId } = useProject();
  const domains = useDomainsQuery(projectId);
  const searchParams = useSearchParams();
  const [adding, setAdding] = useState(false);
  const [domain, setDomain] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [removing, setRemoving] = useState<SenderDomain>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.domains(projectId) });
  const create = useMutation({
    mutationFn: () => api.domains.create(projectId!, domain, { verified: confirmed, active: true }),
    onSuccess: async () => { setAdding(false); setDomain(""); setConfirmed(false); toast("Sender domain recorded.", "success"); await refresh(); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const update = useMutation({
    mutationFn: ({ item, field }: { item: SenderDomain; field: "verified" | "active" }) => api.domains.update(projectId!, item.id, { [field]: !item[field] }),
    onSuccess: async () => { toast("Domain status updated.", "success"); await refresh(); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const remove = useMutation({
    mutationFn: () => api.domains.remove(projectId!, removing!.id),
    onSuccess: async () => { setRemoving(undefined); toast("Sender domain removed.", "success"); await refresh(); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  function submit(event: FormEvent) { event.preventDefault(); create.mutate(); }

  return (
    <div className="page-container">
      <PageHeader eyebrow="Settings" title="Sender domains" description="Record domains already onboarded in Cloudflare Email Service and control which can send." actions={<Button icon={Plus} onClick={() => setAdding(true)}>Add domain</Button>} />
      <SettingsNav />
      {searchParams.get("welcome") ? <div className="notice-banner success-tone"><CheckCircle2 size={19} /><div><strong>Your project is ready</strong><span>Now record a sender domain that is already configured in Cloudflare.</span></div></div> : null}
      <div className="cloudflare-callout"><span><Cloud size={22} /></span><div><h2>Cloudflare remains the source of truth</h2><p>Complete domain onboarding in Cloudflare Email Service first. Then record it here and mark it verified when Cloudflare is ready.</p></div></div>
      {domains.isLoading ? <SkeletonRows count={4} /> : domains.error ? <ErrorState message="Sender domains could not be loaded." onRetry={() => void domains.refetch()} /> : domains.data?.items.length ? (
        <div className="settings-list">
          {domains.data.items.map((item) => (
            <Card className="settings-row domain-row" key={item.id}>
              <span className={`settings-row-icon ${item.verified && item.active ? "verified" : "pending"}`}>{item.verified && item.active ? <CheckCircle2 size={19} /> : <CircleDashed size={19} />}</span>
              <div className="settings-row-main"><div><h2>{item.domain}</h2><span className={`current-chip ${item.verified ? "verified-chip" : "pending-chip"}`}>{item.verified ? "Verified" : "Pending"}</span>{!item.active ? <span className="current-chip disabled-chip">Inactive</span> : null}</div><p>Added {formatDate(item.created_at, { dateStyle: "medium" })}</p></div>
              <div className="settings-row-actions"><Button variant="ghost" size="sm" loading={update.isPending && update.variables?.item.id === item.id} onClick={() => update.mutate({ item, field: "verified" })}>{item.verified ? "Mark unverified" : "Mark verified"}</Button><Button variant="ghost" size="sm" onClick={() => update.mutate({ item, field: "active" })}>{item.active ? "Disable" : "Enable"}</Button><Button variant="ghost" size="icon" onClick={() => setRemoving(item)} aria-label={`Remove ${item.domain}`}><Trash2 size={16} /></Button></div>
            </Card>
          ))}
        </div>
      ) : <Card><EmptyState icon={Globe2} title="No sender domains" description="Record a domain after onboarding it in Cloudflare Email Service." action={<Button icon={Plus} onClick={() => setAdding(true)}>Add sender domain</Button>} /></Card>}
      <Dialog open={adding} onClose={() => setAdding(false)} title="Add sender domain" description="The domain must already exist in your configured Cloudflare account." footer={<><Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button><Button loading={create.isPending} disabled={!domain.trim()} onClick={() => create.mutate()}>Add domain</Button></>}><form className="form-stack" onSubmit={submit}><Field label="Domain"><Input autoFocus required value={domain} onChange={(event) => setDomain(event.target.value.toLowerCase().replace(/^https?:\/\//, "").replace(/\/$/, ""))} placeholder="mail.example.com" /></Field><label className="check-row"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span><strong>Cloudflare shows this domain as ready</strong><small>Mark it verified and allow compose immediately.</small></span></label><button className="sr-only" type="submit">Add domain</button></form></Dialog>
      <Dialog open={Boolean(removing)} onClose={() => setRemoving(undefined)} title="Remove sender domain?" description="New messages can no longer use this domain in Flaremailer." footer={<><Button variant="ghost" onClick={() => setRemoving(undefined)}>Cancel</Button><Button variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate()}>Remove domain</Button></>}><p>Remove <strong>{removing?.domain}</strong>?</p></Dialog>
    </div>
  );
}
