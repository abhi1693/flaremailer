import Link from "next/link";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/dashboard" className="logo" aria-label="Flaremailer home">
      <span className="logo-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      {!compact ? <span>Flaremailer</span> : null}
    </Link>
  );
}
