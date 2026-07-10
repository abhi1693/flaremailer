"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronDown,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Send,
  Settings,
  ShieldBan,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "@/components/logo";
import { ProjectProvider, useProject } from "@/components/project-provider";
import { ErrorState, PageLoader } from "@/components/ui/states";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api-error";
import { initials } from "@/lib/formatters";
import { useSessionQuery } from "@/lib/queries";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/compose", label: "Compose", icon: Send },
  { href: "/templates", label: "Templates", icon: FileText },
  { href: "/suppressions", label: "Suppressions", icon: ShieldBan },
];

function DashboardNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { projects, projectId, setProjectId, isLoading } = useProject();
  const session = useSessionQuery();
  const logout = useMutation({
    mutationFn: api.auth.logout,
    onSettled: () => {
      queryClient.clear();
      window.localStorage.removeItem("flaremailer.project");
      router.replace("/login");
    },
  });

  return (
    <>
      <div className="sidebar-brand"><Logo /></div>
      <div className="project-picker-wrap">
        <span className="sidebar-label">Project</span>
        {isLoading ? (
          <div className="project-picker skeleton-control" />
        ) : projects.length ? (
          <div className="project-picker">
            <span className="project-avatar">{initials(projects.find((item) => item.id === projectId)?.name)}</span>
            <select aria-label="Current project" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <ChevronDown size={14} aria-hidden="true" />
          </div>
        ) : (
          <Link href="/onboarding" className="project-picker empty" onClick={onNavigate}><Plus size={15} /> Create project</Link>
        )}
      </div>
      <nav className="sidebar-nav" aria-label="Main navigation">
        <span className="sidebar-label">Workspace</span>
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(`${href}/`));
          return (
            <Link className={active ? "active" : ""} href={href} key={href} onClick={onNavigate} aria-current={active ? "page" : undefined}>
              <Icon size={18} /><span>{label}</span>{href === "/compose" ? <kbd>C</kbd> : null}
            </Link>
          );
        })}
        <span className="sidebar-label settings-label">Manage</span>
        <Link className={pathname.startsWith("/settings") ? "active" : ""} href="/settings/projects" onClick={onNavigate}>
          <Settings size={18} /><span>Settings</span>
        </Link>
      </nav>
      <div className="sidebar-footer">
        <div className="user-summary">
          <span className="user-avatar">{initials(session.data?.email)}</span>
          <span><strong>Your account</strong><small>{session.data?.email ?? ""}</small></span>
        </div>
        <button onClick={() => logout.mutate()} disabled={logout.isPending} aria-label="Sign out"><LogOut size={17} /></button>
      </div>
    </>
  );
}

function ShellContent({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useSessionQuery();

  useEffect(() => {
    if (session.error instanceof ApiError && session.error.status === 401) {
      queryClient.clear();
      window.localStorage.removeItem("flaremailer.project");
      router.replace("/login");
    }
  }, [queryClient, router, session.error]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if (event.key.toLowerCase() === "c" && !event.metaKey && !event.ctrlKey && !["INPUT", "TEXTAREA", "SELECT"].includes((event.target as HTMLElement).tagName)) {
        router.push("/compose");
      }
    }
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [router]);

  if (session.isLoading) return <PageLoader label="Opening your workspace" />;
  if (session.error instanceof ApiError && session.error.status === 401) return <PageLoader label="Returning to sign in" />;
  if (session.error) {
    return (
      <div className="page-container centered-page">
        <ErrorState message="Your session could not be checked. The API may be unavailable." onRetry={() => void session.refetch()} />
      </div>
    );
  }

  return (
    <div className="dashboard-shell">
      <aside className="sidebar desktop-sidebar"><DashboardNavigation /></aside>
      <header className="mobile-header">
        <Logo />
        <button className="icon-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={21} /></button>
      </header>
      {mobileOpen ? (
        <div className="mobile-nav-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setMobileOpen(false)}>
          <aside className="sidebar mobile-sidebar">
            <button className="mobile-close icon-button" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button>
            <DashboardNavigation onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}
      <main className="dashboard-main">{children}</main>
    </div>
  );
}

export function DashboardShell({ children }: { children: ReactNode }) {
  return <ProjectProvider><ShellContent>{children}</ShellContent></ProjectProvider>;
}
