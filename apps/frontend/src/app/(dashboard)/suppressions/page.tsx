"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, ShieldBan, Trash2 } from "lucide-react";
import { useDeferredValue, useState, type FormEvent } from "react";
import { useProject } from "@/components/project-provider";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/formatters";
import { useSuppressionsQuery } from "@/lib/queries";
import type { Suppression } from "@/lib/types";

export default function SuppressionsPage() {
  const { projectId } = useProject();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<Suppression>();
  const [form, setForm] = useState({ email: "", reason: "manual" });
  const suppressions = useSuppressionsQuery(projectId, deferredSearch);
  const queryClient = useQueryClient();
  const toast = useToast();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["suppressions"] });
  const create = useMutation({
    mutationFn: () => api.suppressions.create(projectId!, form),
    onSuccess: async () => { setAdding(false); setForm({ email: "", reason: "manual" }); toast("Address added to the suppression list.", "success"); await refresh(); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const remove = useMutation({
    mutationFn: () => api.suppressions.remove(projectId!, removing!.id),
    onSuccess: async () => { setRemoving(undefined); toast("Address removed from suppressions.", "success"); await refresh(); },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  function submit(event: FormEvent) { event.preventDefault(); create.mutate(); }

  return (
    <div className="page-container">
      <PageHeader eyebrow="Recipient safety" title="Suppressions" description="Flaremailer will not enqueue email to addresses on this project’s suppression list." actions={<Button icon={Plus} onClick={() => setAdding(true)}>Add address</Button>} />
      <Card className="table-card">
        <div className="table-toolbar"><div className="search-control"><Search size={17} /><Input aria-label="Search suppressed email addresses" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search email address…" /></div><span className="toolbar-count">{suppressions.data?.total ?? 0} suppressed</span></div>
        {suppressions.isLoading ? <SkeletonRows count={7} /> : suppressions.error ? <ErrorState message="Suppressions could not be loaded." onRetry={() => void suppressions.refetch()} /> : suppressions.data?.items.length ? (
          <div className="table-scroll"><table className="data-table"><thead><tr><th>Email address</th><th>Reason</th><th>Added</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{suppressions.data.items.map((item) => <tr key={item.id}><td><span className="recipient-cell"><span className="recipient-avatar blocked"><ShieldBan size={14} /></span><strong>{item.email}</strong></span></td><td><span className="reason-chip">{item.reason}</span></td><td className="muted-cell">{formatDate(item.created_at)}</td><td><Button size="icon" variant="ghost" onClick={() => setRemoving(item)} aria-label={`Remove ${item.email}`}><Trash2 size={16} /></Button></td></tr>)}</tbody></table></div>
        ) : <EmptyState icon={ShieldBan} title={search ? "No matching addresses" : "Suppression list is empty"} description={search ? "Try another email address." : "Manually add addresses that should never receive messages from this project."} action={!search ? <Button variant="secondary" icon={Plus} onClick={() => setAdding(true)}>Add address</Button> : undefined} />}
      </Card>
      <Dialog open={adding} onClose={() => setAdding(false)} title="Suppress an address" description="Future sends to this recipient will be marked suppressed." footer={<><Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button><Button loading={create.isPending} onClick={() => create.mutate()}>Add suppression</Button></>}>
        <form className="form-stack" onSubmit={submit}><Field label="Email address"><Input autoFocus required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="recipient@example.com" /></Field><Field label="Reason"><Textarea rows={3} required maxLength={255} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} /></Field><button className="sr-only" type="submit">Add suppression</button></form>
      </Dialog>
      <Dialog open={Boolean(removing)} onClose={() => setRemoving(undefined)} title="Remove suppression?" description="This address will be eligible to receive new messages again." footer={<><Button variant="ghost" onClick={() => setRemoving(undefined)}>Cancel</Button><Button variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate()}>Remove</Button></>}><p>Allow future sends to <strong>{removing?.email}</strong>?</p></Dialog>
    </div>
  );
}
