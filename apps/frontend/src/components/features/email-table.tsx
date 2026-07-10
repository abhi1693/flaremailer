import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { formatDate, recipientOf } from "@/lib/formatters";
import type { EmailListItem } from "@/lib/types";

export function EmailTable({ items }: { items: EmailListItem[] }) {
  return (
    <div className="table-scroll">
      <table className="data-table email-table">
        <thead>
          <tr><th>Recipient</th><th>Subject</th><th>Status</th><th>Created</th><th><span className="sr-only">Open</span></th></tr>
        </thead>
        <tbody>
          {items.map((email) => (
            <tr key={email.id}>
              <td><span className="recipient-cell"><span className="recipient-avatar">{recipientOf(email)[0]?.toUpperCase()}</span><span>{recipientOf(email)}</span></span></td>
              <td><Link href={`/activity/${email.id}`} className="subject-link">{email.subject || "(No subject)"}</Link></td>
              <td><StatusBadge status={email.status} /></td>
              <td className="muted-cell">{formatDate(email.created_at)}</td>
              <td><Link className="table-open" href={`/activity/${email.id}`} aria-label={`Open ${email.subject}`}><ArrowUpRight size={16} /></Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
