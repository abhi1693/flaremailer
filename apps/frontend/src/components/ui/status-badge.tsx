import { CircleCheck, CircleDashed, CircleX, Clock3, LoaderCircle, ShieldBan } from "lucide-react";
import type { EmailStatus } from "@/lib/types";

const statusMeta = {
  queued: { label: "Queued", icon: Clock3 },
  sending: { label: "Sending", icon: LoaderCircle },
  sent: { label: "Sent", icon: CircleCheck },
  failed: { label: "Failed", icon: CircleX },
  suppressed: { label: "Suppressed", icon: ShieldBan },
} satisfies Record<EmailStatus, { label: string; icon: typeof CircleDashed }>;

export function StatusBadge({ status }: { status: EmailStatus }) {
  const meta = statusMeta[status] ?? { label: status, icon: CircleDashed };
  const Icon = meta.icon;
  return (
    <span className={`status-badge status-${status}`}>
      <Icon size={13} className={status === "sending" ? "spin" : ""} />
      {meta.label}
    </span>
  );
}
