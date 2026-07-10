import type { EmailListItem, Mailbox } from "@/lib/types";

export function formatDate(value?: string | null, options?: Intl.DateTimeFormatOptions) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, options ?? { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function formatCompact(value?: number) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value ?? 0);
}

export function recipientOf(email: EmailListItem) {
  return email.to.length ? email.to.map(mailboxLabel).join(", ") : "Unknown recipient";
}

export function mailboxLabel(mailbox: Mailbox) {
  return mailbox.name ? `${mailbox.name} <${mailbox.email}>` : mailbox.email;
}

export function initials(value?: string | null) {
  if (!value) return "FM";
  return value
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function splitEmails(value: string) {
  return value
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}
