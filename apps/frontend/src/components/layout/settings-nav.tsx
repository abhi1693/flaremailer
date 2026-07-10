"use client";

import { FolderKanban, Globe2, KeyRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const settings = [
  { href: "/settings/projects", label: "Projects", icon: FolderKanban },
  { href: "/settings/domains", label: "Sender domains", icon: Globe2 },
  { href: "/settings/api-keys", label: "API keys", icon: KeyRound },
];

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav className="settings-nav" aria-label="Settings sections">
      {settings.map(({ href, label, icon: Icon }) => (
        <Link key={href} href={href} className={pathname === href ? "active" : ""} aria-current={pathname === href ? "page" : undefined}>
          <Icon size={16} />{label}
        </Link>
      ))}
    </nav>
  );
}
