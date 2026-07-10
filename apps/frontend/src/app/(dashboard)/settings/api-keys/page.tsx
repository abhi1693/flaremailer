"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { SettingsNav } from "@/components/layout/settings-nav";
import { useProject } from "@/components/project-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useApiKeysQuery, useDomainsQuery } from "@/lib/queries";
import type { ApiKey, CreatedApiKey } from "@/lib/types";

export default function ApiKeysSettingsPage() {
  const { projectId } = useProject();
  const keys = useApiKeysQuery(projectId);
  const domains = useDomainsQuery(projectId);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<CreatedApiKey>();
  const [revoking, setRevoking] = useState<ApiKey>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const create = useMutation({
    mutationFn: () => api.apiKeys.create(projectId!, name),
    onSuccess: async (result) => { setCreating(false); setName(""); setCreated(result); await queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys(projectId) }); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const revoke = useMutation({
    mutationFn: () => api.apiKeys.revoke(projectId!, revoking!.id),
    onSuccess: async () => { setRevoking(undefined); toast("API key revoked.", "success"); await queryClient.invalidateQueries({ queryKey: queryKeys.apiKeys(projectId) }); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const keyValue = created?.plaintext ?? "fm_live_your_api_key";
  const sender = domains.data?.items.find((domain) => domain.verified && domain.active)?.domain ?? "mail.example.com";
  const snippet = useMemo(() => `curl -X POST "$FLAREMAILER_URL/api/v1/emails" \\
  -H "Authorization: Bearer ${keyValue}" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: order-123-receipt" \\
  -d '{
    "from": {"email": "hello@${sender}", "name": "Acme"},
    "to": [{"email": "customer@example.com"}],
    "subject": "Your receipt",
    "text": "Thanks for your order!",
    "tags": ["receipt"]
  }'`, [keyValue, sender]);
  function submit(event: FormEvent) { event.preventDefault(); create.mutate(); }

  return (
    <div className="page-container">
      <PageHeader eyebrow="Settings" title="API keys" description="Authenticate project-scoped sends from your applications. Secret values are shown once." actions={<Button icon={Plus} onClick={() => setCreating(true)}>Create API key</Button>} />
      <SettingsNav />
      <div className="api-key-layout">
        <Card className="keys-card">
          <div className="mini-card-head"><div><h2>Project keys</h2><p>Revoke credentials immediately if they are exposed.</p></div><span className="secure-label"><ShieldCheck size={14} />Hashed at rest</span></div>
          {keys.isLoading ? <SkeletonRows count={4} /> : keys.error ? <ErrorState message="API keys could not be loaded." onRetry={() => void keys.refetch()} /> : keys.data?.items.length ? <div className="key-list">{keys.data.items.map((key) => <div className={`key-row ${key.revoked_at ? "revoked" : ""}`} key={key.id}><span className="settings-row-icon"><KeyRound size={17} /></span><div><h3>{key.name}</h3><p><code>{key.prefix}••••••••</code> · Created {formatDate(key.created_at, { dateStyle: "medium" })}</p></div><div className="key-status">{key.revoked_at ? <span className="current-chip disabled-chip">Revoked</span> : <><span>Last used {formatDate(key.last_used_at)}</span><Button size="icon" variant="ghost" onClick={() => setRevoking(key)} aria-label={`Revoke ${key.name}`}><Trash2 size={16} /></Button></>}</div></div>)}</div> : <EmptyState icon={KeyRound} title="No API keys" description="Create a key when you are ready to integrate your application." action={<Button variant="secondary" icon={Plus} onClick={() => setCreating(true)}>Create key</Button>} />}
        </Card>
        <Card className="integration-card"><div className="mini-card-head"><div><h2>Quick integration</h2><p>Send a plain-text test with curl.</p></div><CopyButton value={snippet} /></div><pre><code>{snippet.replace(keyValue, created ? keyValue : "fm_live_••••••••")}</code></pre><p>Use a unique <code>Idempotency-Key</code> for each logical message to make retries safe.</p></Card>
      </div>
      <Dialog open={creating} onClose={() => setCreating(false)} title="Create API key" description="Name the calling service or environment so it is easy to identify later." footer={<><Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button><Button loading={create.isPending} disabled={!name.trim()} onClick={() => create.mutate()}>Create key</Button></>}><form onSubmit={submit}><Field label="Key name"><Input autoFocus required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder="Production API" /></Field><button type="submit" className="sr-only">Create API key</button></form></Dialog>
      <Dialog open={Boolean(created)} onClose={() => setCreated(undefined)} title="Copy your API key now" description="For security, Flaremailer cannot show this secret again." footer={<Button onClick={() => setCreated(undefined)}>I’ve saved it</Button>}><div className="one-time-secret"><div><CheckCircle2 size={20} /><strong>{created?.name} is ready</strong></div><code>{created?.plaintext}</code><CopyButton value={created?.plaintext ?? ""} label="Copy API key" /></div></Dialog>
      <Dialog open={Boolean(revoking)} onClose={() => setRevoking(undefined)} title="Revoke API key?" description="Requests using this key will stop working immediately." footer={<><Button variant="ghost" onClick={() => setRevoking(undefined)}>Cancel</Button><Button variant="danger" icon={Trash2} loading={revoke.isPending} onClick={() => revoke.mutate()}>Revoke key</Button></>}><p>Revoke <strong>{revoking?.name}</strong>?</p></Dialog>
    </div>
  );
}
