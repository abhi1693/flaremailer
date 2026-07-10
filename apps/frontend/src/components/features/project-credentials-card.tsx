"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Eye, EyeOff, KeyRound, LockKeyhole, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/field";
import { ErrorState, SkeletonRows } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { getErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/formatters";
import { queryKeys } from "@/lib/query-keys";
import { useProjectCredentialsQuery } from "@/lib/queries";
import type { Project, ProjectCredentials } from "@/lib/types";

export function ProjectCredentialsCard({ project }: { project?: Project }) {
  const query = useProjectCredentialsQuery(project?.id);
  if (!project) return null;

  const configured = query.data?.configured ?? false;
  const status = query.isLoading ? "Loading…" : query.error ? "Unavailable" : configured ? "Configured" : "Not configured";

  return (
    <section className="project-credentials-section" id="project-credentials" aria-labelledby="project-credentials-title">
      <Card className="project-credentials-card">
        <div className="project-credentials-head">
          <div>
            <h2 id="project-credentials-title"><KeyRound size={17} />Cloudflare sending</h2>
            <p>Provider credentials for <strong>{project.name}</strong>. Each project keeps its own sending configuration.</p>
          </div>
          <span className={`credential-status ${configured ? "configured" : ""}`}>
            {configured ? <CheckCircle2 size={14} /> : <CircleDashed size={14} />}
            {status}
          </span>
        </div>

        {query.isLoading ? <SkeletonRows count={3} /> : query.error ? (
          <ErrorState message="Cloudflare credentials could not be loaded." onRetry={() => void query.refetch()} />
        ) : query.data ? (
          <ProjectCredentialsForm key={`${project.id}:${query.data.updated_at ?? "empty"}`} project={project} credentials={query.data} />
        ) : null}
      </Card>
    </section>
  );
}

function ProjectCredentialsForm({ project, credentials }: { project: Project; credentials: ProjectCredentials }) {
  const [accountId, setAccountId] = useState(credentials.account_id ?? "");
  const [apiToken, setApiToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  const save = useMutation({
    mutationFn: () => {
      const token = apiToken.trim();
      return api.projectCredentials.upsert(project.id, {
        account_id: accountId.trim(),
        ...(token ? { api_token: token } : {}),
      });
    },
    onSuccess: async (result) => {
      queryClient.setQueryData(queryKeys.projectCredentials(project.id), result);
      toast(credentials.configured ? "Cloudflare credentials updated." : "Cloudflare credentials saved.", "success");
      await queryClient.invalidateQueries({ queryKey: queryKeys.projectCredentials(project.id) });
    },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });
  const remove = useMutation({
    mutationFn: () => api.projectCredentials.remove(project.id),
    onSuccess: async () => {
      setConfirmRemove(false);
      queryClient.setQueryData<ProjectCredentials>(queryKeys.projectCredentials(project.id), {
        configured: false,
        account_id: null,
        token_last_four: null,
        updated_at: null,
      });
      toast("Cloudflare credentials removed.", "success");
      await queryClient.invalidateQueries({ queryKey: queryKeys.projectCredentials(project.id) });
    },
    onError: (error) => toast(getErrorMessage(error), "error"),
  });

  const tokenEntered = Boolean(apiToken.trim());
  const tokenValid = !tokenEntered || apiToken.trim().length >= 16;
  const accountChanged = accountId.trim() !== (credentials.account_id ?? "");
  const canSave = Boolean(accountId.trim()) && tokenValid && (credentials.configured ? accountChanged || tokenEntered : tokenEntered);
  const tokenSuffix = credentials.token_last_four ? `••••${credentials.token_last_four}` : "a saved token";

  function submit(event: FormEvent) {
    event.preventDefault();
    if (canSave) save.mutate();
  }

  return (
    <>
      <div className="project-credentials-body">
        <form className="project-credentials-form" onSubmit={submit}>
          {credentials.configured ? (
            <div className="credential-summary">
              <LockKeyhole size={14} aria-hidden="true" />
              Stored token <code>{tokenSuffix}</code>
              {credentials.updated_at ? <> · Updated {formatDate(credentials.updated_at, { dateStyle: "medium" })}</> : null}
            </div>
          ) : null}

          <div className="form-grid">
            <Field label="Cloudflare account ID" hint="Find this on the Cloudflare account overview page.">
              <Input
                required
                autoComplete="off"
                maxLength={128}
                spellCheck={false}
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
                placeholder="023e105f4ecef8ad9ca31a8372d0c353"
              />
            </Field>
            <Field
              label="Cloudflare API token"
              optional={credentials.configured}
              error={tokenEntered && !tokenValid ? "Use at least 16 characters." : undefined}
              hint={credentials.configured ? `Leave blank to keep ${tokenSuffix}; enter a new token to replace it.` : "Required once (at least 16 characters). It will not be shown again after saving."}
            >
              <div className="credential-token-field">
                <Input
                  required={!credentials.configured}
                  autoComplete="new-password"
                  minLength={16}
                  maxLength={2048}
                  spellCheck={false}
                  type={showToken ? "text" : "password"}
                  value={apiToken}
                  onChange={(event) => setApiToken(event.target.value)}
                  placeholder={credentials.configured ? "Leave blank to keep current token" : "Paste an Email Sending API token"}
                />
                <button
                  type="button"
                  onClick={() => setShowToken((visible) => !visible)}
                  aria-label={showToken ? "Hide API token" : "Show API token"}
                >
                  {showToken ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </Field>
          </div>

          <div className="credential-security-note">
            <LockKeyhole size={17} aria-hidden="true" />
            <div>
              <strong>Your API token is write-only</strong>
              <span>Flaremailer encrypts it for this project and never sends the plaintext back to the browser.</span>
            </div>
          </div>

          {save.error ? <div className="inline-error" role="alert">{getErrorMessage(save.error)}</div> : null}

          <div className="project-credentials-actions">
            <div>
              <Button type="submit" loading={save.isPending} disabled={!canSave}>
                {!credentials.configured ? "Save credentials" : tokenEntered ? "Replace credentials" : "Save changes"}
              </Button>
              {credentials.configured ? <Button type="button" variant="ghost" onClick={() => { setAccountId(credentials.account_id ?? ""); setApiToken(""); }}>Reset</Button> : null}
            </div>
            {credentials.configured ? <Button type="button" variant="ghost" icon={Trash2} onClick={() => setConfirmRemove(true)}>Remove credentials</Button> : null}
          </div>
        </form>
      </div>

      <Dialog
        open={confirmRemove}
        onClose={() => setConfirmRemove(false)}
        title="Remove Cloudflare credentials?"
        description="Queued and future messages for this project cannot be sent until new credentials are saved."
        footer={<><Button variant="ghost" onClick={() => setConfirmRemove(false)}>Cancel</Button><Button variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate()}>Remove credentials</Button></>}
      >
        <p>Remove the sending credentials for <strong>{project.name}</strong>?</p>
      </Dialog>
    </>
  );
}
