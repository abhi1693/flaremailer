import type { ReactNode } from "react";
import { Logo } from "@/components/logo";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-layout">
      <div className="auth-brand-panel">
        <Logo />
        <div className="auth-brand-copy">
          <span className="eyebrow light">Transactional email, without the fog</span>
          <h1>Ship messages.<br />See what happened.</h1>
          <p>A clean control plane for reliable transactional email, powered by Cloudflare.</p>
        </div>
        <div className="auth-signal" aria-hidden="true">
          <span className="signal-orbit orbit-one" />
          <span className="signal-orbit orbit-two" />
          <span className="signal-core" />
        </div>
        <p className="auth-footnote">Built for product teams who value a quiet inbox.</p>
      </div>
      <div className="auth-form-panel">{children}</div>
    </main>
  );
}
