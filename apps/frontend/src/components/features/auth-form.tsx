"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { queryKeys } from "@/lib/query-keys";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showPassword, setShowPassword] = useState(false);
  const [values, setValues] = useState({ email: "", password: "" });
  const isRegister = mode === "register";
  const mutation = useMutation({
    mutationFn: () => (isRegister ? api.auth.register(values) : api.auth.login(values)),
    onSuccess: (user) => {
      queryClient.clear();
      window.localStorage.removeItem("flaremailer.project");
      queryClient.setQueryData(queryKeys.me, user);
      router.replace(isRegister ? "/onboarding" : "/dashboard");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="auth-form-wrap">
      <div className="auth-mobile-logo"><span className="logo-mark"><span /><span /><span /></span>Flaremailer</div>
      <div className="auth-heading">
        <span className="eyebrow">{isRegister ? "Start sending" : "Welcome back"}</span>
        <h2>{isRegister ? "Create your account" : "Sign in to Flaremailer"}</h2>
        <p>{isRegister ? "Set up your first project in less than a minute." : "Your delivery workspace is ready when you are."}</p>
      </div>
      <form onSubmit={submit} className="form-stack">
        <Field label="Email address">
          <div className="input-with-icon"><Mail size={17} /><Input type="email" autoComplete="email" required value={values.email} onChange={(e) => setValues({ ...values, email: e.target.value })} placeholder="you@company.com" /></div>
        </Field>
        <Field label="Password" hint={isRegister ? "Use at least 10 characters." : undefined}>
          <div className="input-with-icon input-with-action">
            <LockKeyhole size={17} />
            <Input type={showPassword ? "text" : "password"} minLength={isRegister ? 10 : 1} autoComplete={isRegister ? "new-password" : "current-password"} required value={values.password} onChange={(e) => setValues({ ...values, password: e.target.value })} placeholder="••••••••••" />
            <button type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
          </div>
        </Field>
        {mutation.error ? <div className="inline-error" role="alert">{getErrorMessage(mutation.error)}</div> : null}
        <Button type="submit" size="lg" loading={mutation.isPending}>
          {isRegister ? "Create account" : "Sign in"}<ArrowRight size={17} />
        </Button>
      </form>
      <p className="auth-switch">
        {isRegister ? "Already have an account?" : "New to Flaremailer?"}{" "}
        <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create an account"}</Link>
      </p>
    </div>
  );
}
