"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, FolderKanban, Globe2, KeyRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { queryKeys } from "@/lib/query-keys";

const steps = [
  { icon: FolderKanban, label: "Create a project" },
  { icon: Globe2, label: "Add a sender domain" },
  { icon: KeyRound, label: "Create an API key" },
];

export default function OnboardingPage() {
  const [name, setName] = useState("");
  const router = useRouter();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.projects.create({ name }),
    onSuccess: async (project) => {
      window.localStorage.setItem("flaremailer.project", project.id);
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      router.replace("/settings/domains?welcome=1");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <main className="onboarding-layout">
      <header><Logo /></header>
      <section className="onboarding-grid">
        <div className="onboarding-copy">
          <span className="eyebrow">Three small steps</span>
          <h1>Let’s get your first email moving.</h1>
          <p>Projects keep templates, sender domains, API keys, and activity neatly separated.</p>
          <ol className="onboarding-steps">
            {steps.map(({ icon: Icon, label }, index) => (
              <li className={index === 0 ? "active" : ""} key={label}>
                <span>{index === 0 ? <Icon size={18} /> : <Check size={17} />}</span>
                <div><small>Step {index + 1}</small><strong>{label}</strong></div>
              </li>
            ))}
          </ol>
        </div>
        <div className="onboarding-card card">
          <span className="number-chip">01</span>
          <h2>Name your project</h2>
          <p>Usually your application, service, or environment name.</p>
          <form onSubmit={submit} className="form-stack">
            <Field label="Project name" hint="You can change this later.">
              <Input autoFocus required maxLength={80} value={name} onChange={(event) => setName(event.target.value)} placeholder="Acme Production" />
            </Field>
            {mutation.error ? <div className="inline-error" role="alert">{getErrorMessage(mutation.error)}</div> : null}
            <Button size="lg" type="submit" loading={mutation.isPending}>Continue to sender domain <ArrowRight size={17} /></Button>
          </form>
        </div>
      </section>
    </main>
  );
}
