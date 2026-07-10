"use client";

import { ChevronLeft, ChevronRight, Filter, Search, Send } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { EmailTable } from "@/components/features/email-table";
import { useProject } from "@/components/project-provider";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/field";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/states";
import { useEmailsQuery } from "@/lib/queries";
import type { EmailStatus } from "@/lib/types";

const statuses = ["", "queued", "sending", "sent", "failed", "suppressed"] as const;

export default function ActivityPage() {
  const { projectId } = useProject();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"" | EmailStatus>("");
  const [page, setPage] = useState(1);
  const deferredSearch = useDeferredValue(search);
  const pageSize = 20;
  const messages = useEmailsQuery(projectId, { search: deferredSearch, status: status || undefined, page, pageSize });
  const items = messages.data?.items ?? [];
  const total = messages.data?.total ?? items.length;
  const pages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <PageHeader eyebrow="Message log" title="Activity" description="Search accepted messages by subject, sender, or identifier and inspect their current state." actions={<ButtonLink href="/compose" icon={Send}>Send email</ButtonLink>} />
      <Card className="table-card">
        <div className="table-toolbar">
          <div className="search-control"><Search size={17} /><Input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search subject, sender, or ID…" aria-label="Search activity" /></div>
          <div className="filter-control"><Filter size={16} /><Select value={status} onChange={(event) => { setStatus(event.target.value as "" | EmailStatus); setPage(1); }} aria-label="Filter by status">{statuses.map((item) => <option key={item || "all"} value={item}>{item ? item[0].toUpperCase() + item.slice(1) : "All statuses"}</option>)}</Select></div>
        </div>
        {messages.isLoading ? <SkeletonRows count={8} /> : messages.error ? <ErrorState message="Message activity could not be loaded." onRetry={() => void messages.refetch()} /> : items.length ? (
          <>
            <EmailTable items={items} />
            <div className="table-pagination">
              <span>{total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${total}` : "No results"}</span>
              <div>
                <Button size="icon" variant="ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} aria-label="Previous page"><ChevronLeft size={17} /></Button>
                <span>Page {page} of {pages}</span>
                <Button size="icon" variant="ghost" disabled={page >= pages} onClick={() => setPage((value) => value + 1)} aria-label="Next page"><ChevronRight size={17} /></Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState title={search || status ? "No matching messages" : "No message activity"} description={search || status ? "Try a different search or status filter." : "Send your first transactional email and it will appear here."} action={search || status ? <Button variant="secondary" onClick={() => { setSearch(""); setStatus(""); }}>Clear filters</Button> : <ButtonLink href="/compose">Compose email</ButtonLink>} />
        )}
      </Card>
    </div>
  );
}
