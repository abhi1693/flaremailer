import { CircleAlert, Inbox, LoaderCircle, RefreshCw, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

export function PageLoader({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state-block state-loading" role="status">
      <LoaderCircle className="spin" size={24} />
      <span>{label}…</span>
    </div>
  );
}

export function SkeletonRows({ count = 5 }: { count?: number }) {
  return (
    <div className="skeleton-stack" aria-label="Loading" role="status">
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton-row" key={index} />
      ))}
    </div>
  );
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
}: {
  icon?: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-block empty-state">
      <span className="state-icon"><Icon size={22} /></span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="state-block error-state" role="alert">
      <span className="state-icon"><CircleAlert size={22} /></span>
      <h3>We couldn’t load this</h3>
      <p>{message ?? "Check your connection and try again."}</p>
      {onRetry ? <Button variant="secondary" icon={RefreshCw} onClick={onRetry}>Try again</Button> : null}
    </div>
  );
}
